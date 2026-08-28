"""图形用户界面（tkinter）。

全部 tab 通过直接 import 业务模块调用函数，不再用 subprocess 启动子进程。
后台任务统一走 ``run_async`` helper（threading + queue），进度回调推送 UI。
"""

from .app import FantasyBaseballGUI, run_gui

__all__ = ["FantasyBaseballGUI", "run_gui"]
