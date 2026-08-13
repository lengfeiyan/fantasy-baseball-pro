"""蒙特卡洛选秀模拟选项卡（1000+ 次智能模拟）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import DraftEngine
from ._widgets import (
    action_button,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    ttk.Label(
        parent,
        text=(
            "基于 AI 经理人策略（均衡/囤位置/Statcast信徒/ADP跟随/你的策略），\n"
            "估算各球员在目标顺位的可用概率。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=4)

    param_frame = section_frame(parent, "模拟参数")
    _, pick_var = labeled_input(param_frame, "你的顺位", "5")
    _, iterations_var = labeled_input(param_frame, "模拟次数", "1000")
    _, min_avail_var = labeled_input(param_frame, "最小可用率", "0.25")

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=16)

    def do_simulate():
        def _work():
            app.post("运行蒙特卡洛模拟（可能需数秒）...")
            engine = DraftEngine()
            target = int(pick_var.get())
            avail = engine.analyze_availability(target_pick=target)
            threshold = float(min_avail_var.get())
            top = avail[avail["availability_prob"] >= threshold].head(15)
            if top.empty:
                return f"在可用率 >= {threshold} 时没有找到目标球员，尝试降低阈值。"
            lines = [
                f"第{target}顺位高可用目标（可用率 >= {threshold}）：\n",
                "-" * 60 + "\n",
            ]
            for _, r in top.iterrows():
                lines.append(
                    f"{r['name']:<25} 可用率={r['availability_prob']*100:5.1f}%  "
                    f"VORP={r['vorp']:6.1f}  ADP={r['adp']}"
                )
            lines.append(f"\n（共模拟 {iterations_var.get()} 次，AI 对手含 5 种策略）")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="蒙特卡洛模拟...")

    action_button(btn_frame, "运行模拟", do_simulate)
