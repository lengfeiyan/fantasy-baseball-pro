"""选秀中心选项卡：蛇形选秀 + 蒙特卡洛模拟合并。

上半部分：单次蛇形选秀模拟（quick，看阵容）
下半部分：蒙特卡洛模拟（多次，看可用概率）
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...config import get_config
from ...core import DraftEngine, SnakeDraftSimulator
from ._widgets import (
    action_button,
    labeled_combobox,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    # ===== 上半：蛇形选秀 =====
    draft_frame = section_frame(parent, "单次蛇形选秀模拟")
    cfg = get_config()
    _, pick_var = labeled_input(draft_frame, "选秀顺位", "5")
    _, strategy_var = labeled_combobox(
        draft_frame, "策略",
        ["balanced", "conservative", "aggressive"],
        default=cfg["draft_simulator"]["default_strategy"],
    )
    _, method_var = labeled_combobox(
        draft_frame, "评分方法", ["vorp", "sgp"], default="vorp",
    )

    # ===== 下半：蒙特卡洛 =====
    mc_frame = section_frame(parent, "蒙特卡洛模拟（估算球员可用概率）")
    ttk.Label(
        mc_frame,
        text="基于 ADP/VORP + 随机噪声模拟多次选秀，估算各球员在目标顺位的可用率。",
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=2)
    _, mc_pick_var = labeled_input(mc_frame, "你的顺位", "5")
    _, min_avail_var = labeled_input(mc_frame, "最小可用率", "0.25")

    # 操作按钮 + 输出
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=6)
    _, output = text_display(parent, height=16)

    def do_snake_draft():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()
        pick_s = pick_var.get()
        strategy = strategy_var.get()

        def _work():
            app.post(f"模拟蛇形选秀中（{method.upper()}）...")
            pick = int(pick_s)
            sim = SnakeDraftSimulator(method=method)
            log = sim.simulate_draft(user_pick=pick, strategy=strategy)
            # 传入已算好的 log，避免 simulate_and_save 内部再模拟一遍（修复 L1）
            log_path = sim.simulate_and_save(
                user_pick=pick, strategy=strategy, log_df=log
            )
            user_picks = log[log["team"] == pick]
            value_label = "SGP" if method == "sgp" else "VORP"
            value_key = "sgp_total" if method == "sgp" else "vorp"
            lines = [f"你的阵容（第{pick}顺位，{strategy}策略，{value_label}）：\n"]
            for _, r in user_picks.iterrows():
                mark = " [价值股]" if r.get("is_value_pick") else ""
                lines.append(
                    f"  第{int(r['round'])}轮: {r['name']} ({r['pos']}) "
                    f"{value_label}={r.get(value_key, 0):.1f}{mark}"
                )
            lines.append(f"\n日志已写入数据库（会话保存，支持多模拟对比）")
            lines.append(f"最近一份 CSV：{log_path}")
            lines.append("历史备份：output/history/（时间戳文件，永不覆盖）")
            lines.append("提示：去「阵容验证」页点「从最近模拟导入」即可一键导入这套阵容。")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="模拟选秀...")

    def do_monte_carlo():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()
        target_s = mc_pick_var.get()
        min_avail_s = min_avail_var.get()

        def _work():
            app.post(f"运行蒙特卡洛模拟（{method.upper()}，可能需数秒）...")
            target = int(target_s)
            engine = DraftEngine(method=method)
            avail = engine.analyze_availability(target_pick=target)
            threshold = float(min_avail_s)
            top = avail[avail["availability_prob"] >= threshold].head(15)
            if top.empty:
                return f"在可用率 >= {threshold} 时无目标球员，尝试降低阈值。"
            # 价值列随评分方法变化（SGP 用 sgp_total）
            value_col = "sgp_total" if method == "sgp" else "vorp"
            value_label = "SGP" if method == "sgp" else "VORP"
            lines = [f"第{target}顺位高可用目标（可用率 >= {threshold}）：\n", "-" * 60 + "\n"]
            for _, r in top.iterrows():
                lines.append(
                    f"{r['name']:<25} 可用率={r['availability_prob']*100:5.1f}%  "
                    f"{value_label}={r[value_col]:6.1f}  ADP={r['adp']}"
                )
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="蒙特卡洛模拟...")

    action_button(btn_frame, "单次选秀", do_snake_draft)
    action_button(btn_frame, "蒙特卡洛", do_monte_carlo)
