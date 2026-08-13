"""Statcast 数据查询选项卡。

支持按球员姓名查询（自动搜索 MLB id），展示真实赛季统计 + Statcast 聚合数据。
数据源：MLB Stats API + Baseball Savant。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...data_fetch import MLBStatsClient, StatcastFetcher
from ...utils.logger import get_logger
from ._widgets import (
    action_button,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)

logger = get_logger("gui.statcast")


def create_tab(parent: tk.Widget, app) -> None:
    section_frame(parent, "球员数据查询")
    ttk.Label(
        parent,
        text=(
            "按姓名查询球员的真实赛季统计与 Statcast 数据。\n"
            "数据源：MLB Stats API + Baseball Savant（免费、无需 key）。\n"
            "首次查询需联网，结果会缓存 6-24 小时。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=4)

    _, name_var = labeled_input(parent, "球员姓名", "Shohei Ohtani", width=25)
    _, season_var = labeled_input(parent, "赛季", "2025", width=8)

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=18)

    def do_query():
        def _work():
            name = name_var.get().strip()
            season = int(season_var.get())
            app.post(f"查询 {name} ({season})...")

            client = MLBStatsClient()
            # 1. 搜索球员
            person = client.search_player(name)
            if not person:
                return f"[未找到] 找不到球员：{name}"

            mlb_id = person["id"]
            full_name = person.get("fullName", name)
            pos = person.get("primaryPosition", {}).get("abbreviation", "?")
            app.post(f"找到 {full_name} (id={mlb_id}, pos={pos})，获取统计中...")

            # 2. 赛季统计
            stats = client.fetch_player_stats(mlb_id, season)
            # 3. Statcast
            fetcher = StatcastFetcher()
            if pos in ("P", "TWP"):
                sc = fetcher.fetch_pitcher_data(mlb_id, season)
            else:
                sc = fetcher.fetch_hitter_data(mlb_id, season)

            return _format_result(full_name, pos, mlb_id, stats, sc, season)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="查询中...")

    def do_statcast_only():
        def _work():
            name = name_var.get().strip()
            season = int(season_var.get())
            app.post(f"查询 {name} 的 Statcast...")
            person = MLBStatsClient().search_player(name)
            if not person:
                return f"[未找到] 找不到球员：{name}"
            mlb_id = person["id"]
            pos = person.get("primaryPosition", {}).get("abbreviation", "?")
            fetcher = StatcastFetcher()
            sc = (
                fetcher.fetch_pitcher_data(mlb_id, season)
                if pos in ("P", "TWP")
                else fetcher.fetch_hitter_data(mlb_id, season)
            )
            if not sc:
                return f"{person.get('fullName')} 无 Statcast 数据（可能赛季未投球/打击）。"
            lines = [f"{person.get('fullName')} ({pos}) Statcast ({season})：\n", "-" * 50]
            for k, v in sc.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="Statcast 查询中...")

    action_button(btn_frame, "查询统计+Statcast", do_query)
    action_button(btn_frame, "仅查Statcast", do_statcast_only)


def _format_result(name, pos, mlb_id, stats, sc, season):
    """格式化查询结果。"""
    lines = [f"{name} ({pos}) | MLB id={mlb_id} | {season}赛季\n", "=" * 50]

    if stats and stats.get("stats"):
        lines.append("\n[赛季统计]")
        for k, v in stats["stats"].items():
            if v is not None:
                lines.append(f"  {k:<12}: {v}")
    else:
        lines.append("\n[赛季统计] 无数据（可能赛季未开始或未出赛）")

    if sc:
        lines.append("\n[Statcast]")
        for k, v in sc.items():
            lines.append(f"  {k:<22}: {v}")
    else:
        lines.append("\n[Statcast] 无数据")

    return "\n".join(lines)
