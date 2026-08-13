"""GUI 主窗口骨架。

核心改进（相比旧版 gui_app.py）：
- 消除全部 subprocess.Popen：所有后台任务通过 ``run_async`` 在线程内直接 import 调用。
- 统一的异步执行 helper：进度文本与最终结果/错误通过 queue 回调到 UI 线程。
- 每个 tab 拆为独立文件（gui/tabs/），减少主文件体积。
- 消除 23 处重复 try/except 与 18 处重复 widget 样板。
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from ..utils.logger import get_logger
from .tabs import (
    analysis,
    config_tab,
    data,
    draft_center,
    explore,
    fa_tab,
    home,
    plugins_tab,
    roster,
    sleeper,
)

logger = get_logger("gui")


class TaskCancelled(Exception):
    """用户取消后台任务时抛出（工作线程内）。"""
    pass

# 各 tab 模块的 create 函数映射（顺序即选项卡顺序）
TAB_BUILDERS = [
    ("首页", home.create_tab),
    ("数据管理", data.create_tab),
    ("配置设置", config_tab.create_tab),
    ("分析流水线", analysis.create_tab),
    ("选秀中心", draft_center.create_tab),
    ("阵容验证", roster.create_tab),
    ("Sleeper挖掘", sleeper.create_tab),
    ("FA分析", fa_tab.create_tab),
    ("数据探索", explore.create_tab),
    ("插件管理", plugins_tab.create_tab),
]


class FantasyBaseballGUI:
    """Fantasy Baseball Pro 主窗口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Fantasy Baseball Pro")
        self.root.geometry("900x650")
        self.root.resizable(True, True)

        # 异步任务消息队列（工作线程 → 主线程）
        self._msg_queue: queue.Queue = queue.Queue()
        self._workers: list = []

        # 主框架
        self.main_frame = ttk.Frame(self.root, padding="12")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 选项卡容器
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        logger.info("开始创建功能选项卡")
        for title, builder in TAB_BUILDERS:
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=title)
            try:
                builder(tab, self)
            except Exception as e:
                logger.error("创建选项卡 %s 失败: %s", title, e)
                ttk.Label(tab, text=f"加载失败: {e}").pack()
        logger.info("全部选项卡创建完成")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 进度对话框（懒创建）
        self._progress: Optional[ttk.Progressbar] = None
        self._cancel_btn: Optional[ttk.Button] = None
        # 当前任务的取消信号
        self._cancel_event: Optional[threading.Event] = None

        # 启动队列轮询
        self.root.after(100, self._poll_queue)

    # --------------------------------------------------------- 异步执行
    def run_async(
        self,
        func: Callable[..., Any],
        *,
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[BaseException], None]] = None,
        status: str = "处理中...",
        cancellable: bool = True,
    ) -> threading.Thread:
        """在工作线程执行 func，完成后回调 UI 线程。

        func 内可通过 self.is_cancelled() 检查是否被取消。on_done/on_error 始终在
        UI 线程执行（通过 _msg_queue 调度）。

        Args:
            cancellable: 是否显示取消按钮。短任务可设 False。
        """
        self.set_status(status)
        self._enable_progress(True, cancellable=cancellable)
        self._cancel_event = threading.Event() if cancellable else None

        def worker():
            try:
                result = func()
                self._msg_queue.put(("done", result, on_done))
            except TaskCancelled:
                self._msg_queue.put(("cancelled", None, None))
            except BaseException as e:  # noqa: BLE001
                logger.exception("后台任务失败")
                self._msg_queue.put(("error", e, on_error))

        t = threading.Thread(target=worker, daemon=True)
        self._workers.append(t)
        t.start()
        return t

    def is_cancelled(self) -> bool:
        """工作线程内检查当前任务是否被取消。"""
        return self._cancel_event is not None and self._cancel_event.is_set()

    def post(self, msg: str) -> None:
        """工作线程内推送进度文本（线程安全）。"""
        self._msg_queue.put(("status", msg, None))

    def _cancel_current(self) -> None:
        """用户点击取消按钮时触发。"""
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.set_status("正在取消...")

    def _poll_queue(self) -> None:
        """主线程轮询消息队列，分发回调。"""
        try:
            while True:
                kind, payload, cb = self._msg_queue.get_nowait()
                if kind == "status":
                    self.set_status(str(payload))
                elif kind == "done":
                    self._enable_progress(False)
                    self.set_status("完成")
                    if cb:
                        try:
                            cb(payload)
                        except Exception as e:
                            logger.error("on_done 回调失败: %s", e)
                            messagebox.showerror("错误", str(e))
                elif kind == "cancelled":
                    self._enable_progress(False)
                    self.set_status("已取消")
                elif kind == "error":
                    self._enable_progress(False)
                    self.set_status("出错")
                    if cb:
                        cb(payload)
                    else:
                        messagebox.showerror("错误", str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # --------------------------------------------------------- UI helpers
    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _enable_progress(self, on: bool, cancellable: bool = True) -> None:
        if on:
            if self._progress is None:
                self._progress = ttk.Progressbar(
                    self.status_bar, mode="indeterminate", length=120
                )
            self._progress.pack(side=tk.RIGHT, padx=8)
            self._progress.start(10)
            if cancellable and self._cancel_btn is None:
                self._cancel_btn = ttk.Button(
                    self.status_bar, text="取消", width=4, command=self._cancel_current
                )
            if cancellable and self._cancel_btn is not None:
                self._cancel_btn.pack(side=tk.RIGHT, padx=4)
        else:
            if self._progress is not None:
                self._progress.stop()
                self._progress.pack_forget()
            if self._cancel_btn is not None:
                self._cancel_btn.pack_forget()


def run_gui() -> None:
    """启动 GUI（阻塞）。"""
    root = tk.Tk()
    FantasyBaseballGUI(root)
    logger.info("GUI 应用启动")
    root.mainloop()
