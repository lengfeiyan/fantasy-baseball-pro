"""选秀模拟选项卡（蛇形单次选秀）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...config import get_config
from ...core import SnakeDraftSimulator
from ._widgets import (
    action_button,
    labeled_combobox,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    cfg = get_config()

    param_frame = section_frame(parent, "选秀参数")
    _, pick_var = labeled_input(param_frame, "选秀顺位", "5")
    _, strategy_var = labeled_combobox(
        param_frame,
        "选秀策略",
        ["balanced", "conservative", "aggressive"],
        default=cfg["draft_simulator"]["default_strategy"],
    )

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=16)

    def do_simulate():
        def _work():
            app.post("模拟选秀中...")
            pick = int(pick_var.get())
            sim = SnakeDraftSimulator()
            log_path = sim.simulate_and_save(user_pick=pick, strategy=strategy_var.get())
            log = sim.simulate_draft(user_pick=pick, strategy=strategy_var.get())
            user_picks = log[log["team"] == pick]
            lines = [f"你的阵容（第{pick}顺位，{strategy_var.get()}策略）：\n"]
            for _, r in user_picks.iterrows():
                value_mark = " [价值股]" if r.get("is_value_pick") else ""
                lines.append(
                    f"  第{int(r['round'])}轮: {r['name']} ({r['pos']}) "
                    f"VORP={r['vorp']:.1f}{value_mark}"
                )
            lines.append(f"\n选秀日志已保存：{log_path}")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="模拟选秀...")

    action_button(btn_frame, "模拟选秀", do_simulate)
