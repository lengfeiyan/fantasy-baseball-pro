"""插件管理选项卡。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...plugins import PluginManager
from ._widgets import action_button, section_frame, set_text, text_display


def create_tab(parent: tk.Widget, app) -> None:
    section_frame(parent, "插件管理")
    ttk.Label(
        parent,
        text=(
            "管理已加载的插件。\n"
            "插件放在项目根的 plugins/ 目录下（每个插件一个子目录，含 __init__.py）。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=4)

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=14)

    def do_refresh():
        pm = PluginManager()
        pm.load_plugins()
        plugins = pm.get_all_plugins()
        if not plugins:
            set_text(output, "暂无已加载插件。把插件放到 plugins/ 目录后点击刷新。")
            return
        lines = [f"已加载 {len(plugins)} 个插件：\n", "-" * 50]
        for name, plugin in plugins.items():
            info = plugin.get_info()
            enabled = "[启用]" if name in pm.get_enabled_plugins() else "[禁用]"
            lines.append(f"{enabled} {name} v{info['version']} - {info['description']}")
        set_text(output, "\n".join(lines))
        app.set_status(f"加载 {len(plugins)} 个插件")

    action_button(btn_frame, "刷新插件", do_refresh)
