"""新秀雷达选项卡（F7）：选秀 sleeper 榜（Pipeline 先验 + Statcast 分层数据）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core.rookies import RookieRadar
from ...data_fetch.mlb_api import MLBStatsClient
from ._widgets import (
    action_button,
    fill_table,
    labeled_combobox,
    labeled_input,
    section_frame,
    table_display,
)

# 表格列定义（key, 标题, 宽度, 对齐）
_COLUMNS = [
    ("composite", "综合", 60, "e"),
    ("pipeline_rank", "榜", 40, "center"),
    ("name", "姓名", 150, "w"),
    ("position", "位置", 50, "center"),
    ("team", "队", 45, "center"),
    ("age", "龄", 40, "center"),
    ("level", "级", 45, "center"),
    ("tier", "层", 40, "center"),
    ("proximity", "近度", 55, "center"),
    ("signals", "信号", 300, "w"),
    ("adp", "ADP", 60, "e"),
    ("value_gap", "差值", 55, "e"),
]


def create_tab(parent: tk.Widget, app) -> None:
    param_frame = section_frame(parent, "筛选参数（数据层级 A=MLB百分位 B=MiLB Statcast C=比率统计 D=春训）")
    _, top_var = labeled_input(param_frame, "显示数量", "20")
    _, pos_var = labeled_combobox(
        param_frame,
        "位置筛选",
        ["All", "C", "1B", "2B", "3B", "SS", "OF", "SP", "RP"],
        default="All",
    )
    include_far = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        param_frame, text="含「远」接近度（ETA 2028+，redraft 一般用不上）",
        variable=include_far,
    ).pack(anchor=tk.W)
    use_spring = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        param_frame, text="启用春训数据（Tier D，选秀窗口 2-3 月才新鲜）",
        variable=use_spring,
    ).pack(anchor=tk.W)
    force = tk.BooleanVar(value=False)
    ttk.Checkbutton(param_frame, text="强刷缓存（默认 7 天）", variable=force).pack(anchor=tk.W)

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=6)
    _, tree = table_display(parent, _COLUMNS, height=18)

    def _row_dicts(df) -> list:
        rows = []
        for _, r in df.iterrows():
            adp = r["adp"]
            gap = r["value_gap"]
            rows.append({
                "composite": f"{r['composite']:.3f}",
                "pipeline_rank": int(r["pipeline_rank"]),
                "name": r["name"],
                "position": r["position"],
                "team": r["team"] or "—",
                "age": int(r["age"]),
                "level": r["level"],
                "tier": r["tier"],
                "proximity": r["proximity"],
                "signals": r["signals"],
                "adp": f"{adp:.0f}" if adp == adp and adp is not None else "—",
                "value_gap": f"{gap:+.0f}" if gap == gap and gap is not None else "—",
            })
        return rows

    def do_build():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        top_n = int(top_var.get() or 20)
        pos = pos_var.get()
        want_far = include_far.get()
        want_spring = use_spring.get()
        want_force = force.get()

        def _work():
            app.post("抓取 Pipeline 榜单与 Statcast 快照...")
            radar = RookieRadar(stats_client=MLBStatsClient())
            df = radar.build(include_far=want_far, use_spring=want_spring, force=want_force)
            if df.empty:
                return []
            if pos != "All":
                df = df[df["position"] == pos]
            try:
                RookieRadar.save_snapshot(df)
                app.post(f"快照已入库（{len(df)} 条）")
            except Exception:
                pass  # 入库失败不影响展示
            return _row_dicts(df.head(top_n))

        def _done(rows):
            fill_table(tree, rows)
            app.set_status(f"新秀雷达：{len(rows)} 人")

        def _err(e):
            fill_table(tree, [])
            app.set_status(f"生成失败：{e}")

        app.run_async(_work, on_done=_done, on_error=_err, status="生成新秀雷达榜...")

    action_button(btn_frame, "生成榜单", do_build)
