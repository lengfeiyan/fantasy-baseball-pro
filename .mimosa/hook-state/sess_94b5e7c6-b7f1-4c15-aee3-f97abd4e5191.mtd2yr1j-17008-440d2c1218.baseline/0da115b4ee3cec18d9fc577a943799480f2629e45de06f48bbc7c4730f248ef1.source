"""伤病分析选项卡。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...db import InjuryRepository, db_session
from ._widgets import action_button, section_frame, set_text, text_display


def create_tab(parent: tk.Widget, app) -> None:
    section_frame(parent, "伤病报告")
    ttk.Label(
        parent,
        text="查看数据库中的伤病报告。使用 FA分析 选项卡的「更新伤病」按钮获取最新数据。",
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=4)

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=14)

    def do_list():
        with db_session() as conn:
            df = InjuryRepository(conn).get_all()
        if df.empty:
            set_text(output, "暂无伤病数据。")
            return
        lines = [f"伤病报告（共 {len(df)} 条）：\n", "-" * 60]
        for _, r in df.iterrows():
            lines.append(
                f"{r['name']:<20} {r.get('injury_type', '')}  "
                f"严重度={r.get('severity', '')}  状态={r.get('status', '')}"
            )
        set_text(output, "\n".join(lines))
        app.set_status(f"显示 {len(df)} 条伤病记录")

    action_button(btn_frame, "查看伤病列表", do_list)
