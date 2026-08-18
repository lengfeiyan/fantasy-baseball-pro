"""Sleeper 挖掘选项卡。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import find_sleepers
from ._widgets import (
    action_button,
    labeled_combobox,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    param_frame = section_frame(parent, "筛选参数")
    _, min_adp_var = labeled_input(param_frame, "最小ADP", "80")
    _, max_adp_var = labeled_input(param_frame, "最大ADP", "300")
    _, min_bias_var = labeled_input(param_frame, "最小低估", "30")
    _, top_var = labeled_input(param_frame, "返回数量", "15")
    _, pos_var = labeled_combobox(
        param_frame,
        "位置筛选",
        ["All", "C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "UTIL"],
        default="All",
    )
    use_statcast = tk.BooleanVar(value=True)
    ttk.Checkbutton(param_frame, text="启用Statcast增强", variable=use_statcast).pack(anchor=tk.W)

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=16)

    def do_find():
        # UI 线程先取值（Tk 变量不支持跨线程访问）；int 转换留在工作线程，
        # 失败仍走 run_async 的中文错误弹窗
        position = pos_var.get()
        min_adp_s, max_adp_s, min_bias_s, top_s = (
            min_adp_var.get(), max_adp_var.get(), min_bias_var.get(), top_var.get()
        )
        use_sc = bool(use_statcast.get())

        def _work():
            app.post("挖掘 Sleeper 中...")
            df = find_sleepers(
                min_adp=int(min_adp_s),
                max_adp=int(max_adp_s),
                min_bias=int(min_bias_s),
                top=int(top_s),
                position=None if position == "All" else position,
                use_statcast=use_sc,
            )
            if df.empty:
                return "未找到符合条件的 Sleeper 球员。"
            lines = [f"发现 {len(df)} 个 Sleeper 候选：\n", "-" * 60 + "\n"]
            for _, r in df.iterrows():
                sc = f" [Statcast: {r['statcast_signal']}]" if r.get("statcast_signal") else ""
                lines.append(
                    f"{r['name']} ({r.get('pos', '')})  ADP={r['adp']}  偏差={r['bias']}{sc}"
                )
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="挖掘Sleeper...")

    action_button(btn_frame, "挖掘Sleeper", do_find)
