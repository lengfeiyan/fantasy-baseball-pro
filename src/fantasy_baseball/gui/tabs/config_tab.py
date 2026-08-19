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

    # 可滚动容器：配置区块多（7 个区块 30+ 行输入框），单列会超出可视区域
    canvas = tk.Canvas(parent, highlightthickness=0)
    vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, padding="4")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    # 内容宽度跟随画布（避免窗口拉宽后右侧留白/内容截断）
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_wheel(e):
        # Windows 滚轮：delta ±120
        canvas.yview_scroll(int(-e.delta / 120), "units")
        return "break"  # 阻止其他控件（如下拉框）重复响应

    # 鼠标在配置页内才接管滚轮，离开即还回（bind_all 是全局的）
    canvas.bind("<Enter>", lambda e: parent.bind_all("<MouseWheel>", _on_wheel))
    canvas.bind("<Leave>", lambda e: parent.unbind_all("<MouseWheel>"))

    # 三列布局：SGP 分母独占一列（10 行输入，与其他两列高度相近）
    col1 = ttk.Frame(inner)
    col1.grid(row=0, column=0, sticky="nw", padx=(0, 10))
    col2 = ttk.Frame(inner)
    col2.grid(row=0, column=1, sticky="nw", padx=(0, 10))
    col3 = ttk.Frame(inner)
    col3.grid(row=0, column=2, sticky="nw")
    for i in range(3):
        inner.columnconfigure(i, weight=1)

    # 联盟设置
    league_frame = section_frame(col1, "联盟设置")
    _, size_var = labeled_input(league_frame, "联盟规模", str(cfg["league"]["size"]))
    _, rounds_var = labeled_input(league_frame, "选秀轮数", str(cfg["league"]["rounds"]))

    # 打者评分权重
    hitter_frame = section_frame(col1, "打者评分权重")
    hitter_vars = {}
    for stat, w in cfg["league"]["scoring"]["hitters"].items():
        _, v = labeled_input(hitter_frame, stat, str(w))
        hitter_vars[stat] = v

    # 投手评分权重
    pitcher_frame = section_frame(col1, "投手评分权重")
    pitcher_vars = {}
    for stat, w in cfg["league"]["scoring"]["pitchers"].items():
        _, v = labeled_input(pitcher_frame, stat, str(w))
        pitcher_vars[stat] = v

    # 阵容槽位
    roster_frame = section_frame(col2, "阵容槽位")
    roster_vars = {}
    for pos, count in cfg["league"]["roster_slots"].items():
        _, v = labeled_input(roster_frame, pos, str(count), width=5)
        roster_vars[pos] = v

    # 选秀策略
    draft_frame = section_frame(col2, "选秀策略")
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
    adv_frame = section_frame(col2, "评分与风险")
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
        foreground="gray", wraplength=260, justify=tk.LEFT,
    ).pack(anchor=tk.W)

    # SGP 分母（独占第三列，修复 M6：新增，12 队经验值为默认）
    sgp_frame = section_frame(col3, "SGP 分母")
    ttk.Label(
        sgp_frame,
        text="每升一名所需统计量（12 队经验值，计数类按联盟规模自动缩放）",
        foreground="gray", wraplength=240, justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(0, 4))
    ttk.Label(sgp_frame, text="打者", font=("", 9, "bold")).pack(anchor=tk.W)
    sgp_hitter_vars = {}
    for stat, d in cfg.get("sgp", {}).get("denominators", {}).get("hitters", {}).items():
        _, v = labeled_input(sgp_frame, stat, str(d), width=8)
        sgp_hitter_vars[stat] = v
    ttk.Label(sgp_frame, text="投手", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 0))
    sgp_pitcher_vars = {}
    for stat, d in cfg.get("sgp", {}).get("denominators", {}).get("pitchers", {}).items():
        _, v = labeled_input(sgp_frame, stat, str(d), width=8)
        sgp_pitcher_vars[stat] = v

    # 保存按钮（横跨三列）
    btn_frame = ttk.Frame(inner)
    btn_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 4))

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
