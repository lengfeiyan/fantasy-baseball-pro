"""配置设置选项卡。

直接读写 config.yaml（通过 yaml），不再 subprocess。保存后使配置缓存失效。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...config import get_config, save_config_values
from ...utils.logger import get_logger
from ._widgets import action_button, labeled_input, section_frame

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

    # 选秀策略
    draft_frame = section_frame(parent, "选秀策略")
    _, strategy_var = labeled_input(
        draft_frame, "默认策略", cfg["draft_simulator"]["default_strategy"]
    )

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
            }
            for stat, var in hitter_vars.items():
                updates[f"league.scoring.hitters.{stat}"] = float(var.get())
            for stat, var in pitcher_vars.items():
                updates[f"league.scoring.pitchers.{stat}"] = float(var.get())

            save_config_values(updates)
            messagebox.showinfo("成功", "配置已保存（注释已保留）")
            app.set_status("配置已保存")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    action_button(btn_frame, "保存配置", save)
