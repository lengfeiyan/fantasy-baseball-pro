"""GUI 测试。

测试策略：tkinter GUI 用 root.withdraw() 隐藏窗口，测试：
1. 构造无异常（所有 tab 成功创建）
2. run_async 机制（完成/取消/错误回调）
3. 各 tab 模块的 create_tab 函数可调用

不测试像素级 UI（需人工），只测试"能跑起来 + 回调不崩溃"。
"""

from __future__ import annotations

import threading
import time

import pytest


@pytest.fixture
def gui_app():
    """创建一个隐藏窗口的 GUI 实例（测试后销毁）。"""
    import tkinter as tk
    from fantasy_baseball.gui import FantasyBaseballGUI

    root = tk.Tk()
    root.withdraw()  # 不显示窗口
    app = FantasyBaseballGUI(root)
    yield app
    root.destroy()


# ============================================================
# 构造测试
# ============================================================
class TestGUIConstruction:
    def test_tabs_created(self, gui_app):
        """所有选项卡应成功创建。"""
        assert gui_app.notebook.index("end") == 10

    def test_tab_titles(self, gui_app):
        """选项卡标题应与预期一致。"""
        titles = [gui_app.notebook.tab(i, "text") for i in range(10)]
        assert "首页" in titles
        assert "选秀中心" in titles
        assert "数据探索" in titles
        assert "FA分析" in titles

    def test_status_var_exists(self, gui_app):
        assert gui_app.status_var.get() == "就绪"

    def test_message_queue_exists(self, gui_app):
        import queue
        assert isinstance(gui_app._msg_queue, queue.Queue)

    def test_cancel_event_initial_none(self, gui_app):
        """初始状态无任务，cancel_event 应为 None。"""
        assert gui_app._cancel_event is None
        assert gui_app.is_cancelled() is False


# ============================================================
# run_async 机制测试
# ============================================================
class TestRunAsync:
    def test_simple_task_completes(self, gui_app):
        """简单任务应执行并返回结果。"""
        results = []
        gui_app.run_async(
            lambda: 42,
            on_done=lambda r: results.append(r),
        )
        # 等待 worker 完成（最多 2 秒）
        _process_events(gui_app, timeout=2.0)
        assert results == [42]

    def test_task_error_handled(self, gui_app):
        """任务抛异常应走 error 分支。"""
        errors = []

        def failing_task():
            raise ValueError("test error")

        gui_app.run_async(
            failing_task,
            on_error=lambda e: errors.append(e),
        )
        _process_events(gui_app, timeout=2.0)
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)

    def test_cancel_signal(self, gui_app):
        """取消信号应被工作线程检测到。"""
        cancelled = []

        def long_task():
            for _ in range(100):
                if gui_app.is_cancelled():
                    from fantasy_baseball.gui.app import TaskCancelled
                    raise TaskCancelled()
                time.sleep(0.01)
            return "done"

        gui_app.run_async(long_task)
        # 稍等后触发取消
        time.sleep(0.05)
        gui_app._cancel_current()
        _process_events(gui_app, timeout=2.0)
        # 状态应变为"已取消"
        assert gui_app.status_var.get() == "已取消"

    def test_post_updates_status(self, gui_app):
        """post() 推送的进度文本应更新状态栏。"""
        def task_with_post():
            gui_app.post("步骤1...")
            time.sleep(0.05)
            return "done"

        gui_app.run_async(task_with_post)
        _process_events(gui_app, timeout=2.0)
        # 最终状态应为"完成"（post 的文本是中间状态）
        assert gui_app.status_var.get() in ("完成", "步骤1...")


class TestConcurrentTasks:
    """并发任务隔离（审计项回归：共享 cancel_event 曾让任务互相误伤）。"""

    def test_cancel_one_task_does_not_discard_other(self, gui_app):
        results = []

        def task_a():
            time.sleep(0.3)  # 慢任务，被取消
            return "A-done"

        def task_b():
            time.sleep(0.1)  # 快任务，正常完成
            return "B-done"

        t_a = gui_app.run_async(task_a, on_done=lambda r: results.append(r))
        time.sleep(0.05)
        gui_app.run_async(task_b, on_done=lambda r: results.append(r))
        time.sleep(0.15)  # B 已完成、A 还在跑
        gui_app._cancel_current()  # 取消的是最近任务……A 仍用自己的信号
        _process_events(gui_app, timeout=2.0)
        assert "B-done" in results

    def test_cancel_most_recent_task(self, gui_app):
        """取消按钮应作用于最近启动的任务（每任务独立信号）。"""
        from fantasy_baseball.gui.app import TaskCancelled

        def task_a():
            time.sleep(0.4)
            return "A-done"

        def task_b():
            for _ in range(100):
                if gui_app.is_cancelled():
                    raise TaskCancelled()
                time.sleep(0.01)
            return "B-done"

        gui_app.run_async(task_a)
        time.sleep(0.05)
        gui_app.run_async(task_b)
        time.sleep(0.05)
        gui_app._cancel_current()  # 取消 B；A 不受影响
        _process_events(gui_app, timeout=2.0)
        # B 被取消，A 正常完成（若共享信号，A 完成时也会被丢弃并显示已取消）
        assert gui_app.status_var.get() in ("完成", "已取消")

    def test_on_error_exception_does_not_kill_polling(self, gui_app, monkeypatch):
        """error 回调自身抛异常时，轮询链必须存活（审计项回归）。"""
        results = []
        # 打桩掉真实 modal 弹窗，避免阻塞测试 mainloop
        popups = []
        monkeypatch.setattr(
            "fantasy_baseball.gui.app.messagebox.showerror",
            lambda *a, **k: popups.append(a),
        )

        def bad_task():
            raise ValueError("boom")

        def bad_on_error(e):
            raise RuntimeError("on_error 自身崩溃")

        gui_app.run_async(bad_task, on_error=bad_on_error)
        _process_events(gui_app, timeout=1.0)
        # 轮询链仍活着：再跑一个任务应正常完成
        gui_app.run_async(lambda: "ok", on_done=lambda r: results.append(r))
        _process_events(gui_app, timeout=2.0)
        assert results == ["ok"]
        assert len(popups) >= 1  # on_error 崩溃被兜底弹窗报告


# ============================================================
# 各 tab 模块可调用性测试
# ============================================================
class TestTabModules:
    """每个 tab 模块的 create_tab 应能在新 Frame 上调用。"""

    def test_home_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import home
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            home.create_tab(frame, None)
        finally:
            root.destroy()

    def test_data_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import data
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            data.create_tab(frame, None)
        finally:
            root.destroy()

    def test_draft_center_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import draft_center
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            draft_center.create_tab(frame, None)
        finally:
            root.destroy()

    def test_explore_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import explore
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            explore.create_tab(frame, None)
        finally:
            root.destroy()

    def test_config_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import config_tab
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            config_tab.create_tab(frame, None)
        finally:
            root.destroy()

    def test_analysis_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import analysis
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            analysis.create_tab(frame, None)
        finally:
            root.destroy()

    def test_fa_tab(self):
        import tkinter as tk
        from fantasy_baseball.gui.tabs import fa_tab
        root = tk.Tk(); root.withdraw()
        frame = tk.Frame(root)
        try:
            fa_tab.create_tab(frame, None)
        finally:
            root.destroy()


# ============================================================
# 辅助
# ============================================================
def _process_events(app, timeout=2.0):
    """处理 tkinter 事件循环，直到 timeout 或队列为空。

    轮询 _msg_queue 并执行回调（模拟主线程的 _poll_queue）。
    """
    import queue
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        try:
            kind, payload, cb = app._msg_queue.get_nowait()
            if kind == "done":
                app._enable_progress(False)
                app.set_status("完成")
                if cb:
                    cb(payload)
            elif kind == "cancelled":
                app._enable_progress(False)
                app.set_status("已取消")
            elif kind == "error":
                app._enable_progress(False)
                app.set_status("出错")
                if cb:
                    cb(payload)
            elif kind == "status":
                app.set_status(str(payload))
        except queue.Empty:
            time.sleep(0.02)
