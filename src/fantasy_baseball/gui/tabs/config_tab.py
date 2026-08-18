"""配置设置选项卡。

直接读写 config.yaml（通过 yaml），不再 subprocess。保存后使配置缓存失效。
修复 M6：补全 risk_model / scoring.stream_slots / sgp 分母 / show_value_picks
的编辑能力（此前这些只能手改 YAML）。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...config import get_config, save_config_values
from ...utils.logger import get_logger
from ..errors import friendly_error
from ._widgets import action_button, labeled_combobox, labeled_input, section_frame

logger = get_logger("gui.config")


def create_tab(parent: tk.Widget, app) -> None:
    cfg = get_config()

    # 联盟设置
    league_frame = section_frame(parent, "联盟设置")
    _, size_var = labeled_input(league_frame, "联盟规模", str(cfg["league"]["size"]))
    _, rounds_var = labeled_input(league_frame, "选秀轮数", str(cfg["league"]["rounds"]))

    # 打者评分权重
    hitter_frame = section_frame(parent, "打者评分权重")
    hitter_vars = {}
    for stat, w in cfg["league"]["scoring"]["hitters"].items():
        _, v = labeled_input(hitter_frame, stat, str(w))
        hitter_vars[stat] = v

    # 投手评分权重
    pitcher_frame = section_frame(parent, "投手评分权重")
    pitcher_vars = {}
    for stat, w in cfg["league"]["scoring"]["pitchers"].items():
        _, v = labeled_input(pitcher_frame, stat, str(w))
        pitcher_vars[stat] = v

    # 阵容槽位
    roster_frame = section_frame(parent, "阵容槽位")
    roster_vars = {}
    for pos, count in cfg["league"]["roster_slots"].items():
        _, v = labeled_input(roster_frame, pos, str(count), width=5)
        roster_vars[pos] = v

    # 选秀策略
    draft_frame = section_frame(parent, "选秀策略")
    _, strategy_var = labeled_combobox(
        draft_frame, "默认策略",
        ["balanced", "conservative", "aggressive"],
        default=cfg["draft_simulator"]["default_strategy"],
    )
    _, value_picks_var = labeled_combobox(
        draft_frame, "价值股标记",
        ["true", "false"],
        default=str(cfg["draft_simulator"].get("show_value_picks", True)).lower(),
    )

    # 评分与风险（修复 M6：新增）
    adv_frame = section_frame(parent, "评分与风险")
    _, stream_var = labeled_input(
        adv_frame, "stream席位数",
        str(cfg.get("scoring", {}).get("stream_slots", 5)), width=5,
    )
    _, risk_factor_var = labeled_input(
        adv_frame, "风险调整系数",
        str(cfg.get("risk_model", {}).get("adjustment_factor", 0.1)), width=8,
    )
    ttk.Label(
        adv_frame,
        text="（stream 席位：日替/轮换位置的球员数，影响动态替代水平；风险系数越大 upside/floor 差异越大）",
        foreground="gray",
    ).pack(anchor=tk.W)

    # SGP 分母（修复 M6：新增，12 队经验值为默认）
    sgp_frame = section_frame(parent, "SGP 分母（每升一名所需统计量，12 队经验值）")
    sgp_hitter_vars = {}
    for stat, d in cfg.get("sgp", {}).get("denominators", {}).get("hitters", {}).items():
        _, v = labeled_input(sgp_frame, stat, str(d), width=8)
        sgp_hitter_vars[stat] = v
    sgp_pitcher_vars = {}
    for stat, d in cfg.get("sgp", {}).get("denominators", {}).get("pitchers", {}).items():
        _, v = labeled_input(sgp_frame, stat, str(d), width=8)
        sgp_pitcher_vars[stat] = v

    # 保存按钮
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)

    def save():
        try:
            # 用 save_config_values 逐行更新，保留注释
            updates = {
                "league.size": int(size_var.get()),
                "league.rounds": int(rounds_var.get()),
                "draft_simulator.default_strategy": strategy_var.get().strip(),
                "draft_simulator.show_value_picks": value_picks_var.get() == "true",
                "scoring.stream_slots": int(stream_var.get()),
                "risk_model.adjustment_factor": float(risk_factor_var.get()),
            }
            for stat, var in hitter_vars.items():
                updates[f"league.scoring.hitters.{stat}"] = float(var.get())
            for stat, var in pitcher_vars.items():
                updates[f"league.scoring.pitchers.{stat}"] = float(var.get())
            for pos, var in roster_vars.items():
                updates[f"league.roster_slots.{pos}"] = int(var.get())
            for stat, var in sgp_hitter_vars.items():
                updates[f"sgp.denominators.hitters.{stat}"] = float(var.get())
            for stat, var in sgp_pitcher_vars.items():
                updates[f"sgp.denominators.pitchers.{stat}"] = float(var.get())

            missing = save_config_values(updates)
            if missing:
                messagebox.showwarning(
                    "部分保存",
                    "以下配置项在 config.yaml 中未找到，未保存：\n"
                    + "\n".join(missing)
                    + "\n其余配置已保存（注释已保留）。",
                )
            else:
                messagebox.showinfo("成功", "配置已保存（注释已保留）")
            app.set_status("配置已保存")
        except Exception as e:
            messagebox.showerror("错误", friendly_error(e))

    action_button(btn_frame, "保存配置", save)
