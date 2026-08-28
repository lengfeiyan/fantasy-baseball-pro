"""数据探索选项卡：Statcast 查询 + 伤病列表合并。

上半部分：按姓名查询球员的真实赛季统计 + Statcast
下半部分：查看伤病列表
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...data_fetch import MLBStatsClient, StatcastFetcher
from ...db import InjuryRepository, db_session
from ._widgets import (
    action_button,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    # ===== 上半：球员数据查询 =====
    query_frame = section_frame(parent, "球员数据查询（MLB Stats API + Baseball Savant）")
    _, name_var = labeled_input(query_frame, "球员姓名", "Shohei Ohtani", width=25)
    # 修复 M10：默认当前年（修复前硬编码 2025）
    import datetime
    _, season_var = labeled_input(query_frame, "赛季", str(datetime.datetime.now().year), width=8)

    # ===== 下半：伤病列表 =====
    injury_frame = section_frame(parent, "伤病报告")

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=6)
    _, output = text_display(parent, height=16)

    def do_query():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        name = name_var.get().strip()
        season_s = season_var.get()

        def _work():
            season = int(season_s)
            app.post(f"查询 {name} ({season})...")

            client = MLBStatsClient()
            person = client.search_player(name)
            if not person:
                return f"[未找到] 找不到球员：{name}"

            mlb_id = person["id"]
            full_name = person.get("fullName", name)
            pos = person.get("primaryPosition", {}).get("abbreviation", "?")

            stats = client.fetch_player_stats(mlb_id, season)
            fetcher = StatcastFetcher()
            sc = (
                fetcher.fetch_pitcher_data(mlb_id, season)
                if pos in ("P", "TWP")
                else fetcher.fetch_hitter_data(mlb_id, season)
            )

            lines = [f"{full_name} ({pos}) | MLB id={mlb_id} | {season}赛季\n", "=" * 50]
            if stats and stats.get("stats"):
                lines.append("\n[赛季统计]")
                for k, v in stats["stats"].items():
                    if v is not None:
                        lines.append(f"  {k:<12}: {v}")
            else:
                lines.append("\n[赛季统计] 无数据")

            if sc:
                lines.append("\n[Statcast]")
                for k, v in sc.items():
                    lines.append(f"  {k:<22}: {v}")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="查询中...")

    def do_injuries():
        with db_session() as conn:
            df = InjuryRepository(conn).get_all()
        if df.empty:
            set_text(output, "暂无伤病数据。去「FA分析」选项卡点「更新伤病」获取。")
            return
        lines = [f"伤病报告（{len(df)} 条）：\n", "-" * 60]
        for _, r in df.iterrows():
            lines.append(
                f"  {r.get('team',''):<18} {r['name']:<20} {r.get('severity',''):<10} {r.get('injury_type','')}"
            )
        set_text(output, "\n".join(lines))
        app.set_status(f"伤病: {len(df)} 条")

    action_button(btn_frame, "查询球员", do_query)
    action_button(btn_frame, "查看伤病", do_injuries)
