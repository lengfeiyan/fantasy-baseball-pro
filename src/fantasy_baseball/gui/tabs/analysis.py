"""分析流水线选项卡：导入 → 排名 → ADP。"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from ...config import find_output_file, get_season
from ...core import ADPCache, DataIngestor, ScoringModel
from ._widgets import (
    action_button,
    labeled_combobox,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    section_frame(parent, "分析流水线")
    ttk.Label(
        parent,
        text=(
            "一键运行完整流程：\n"
            "  1. 导入数据（网络或 CSV）\n"
            "  2. 生成排名（VORP 或 SGP）\n"
            "  3. 准备 ADP 数据（缓存）\n\n"
            "也可单独执行某一步。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=6)

    # 评分方法选择
    _, method_var = labeled_combobox(
        parent, "评分方法", ["vorp", "sgp"], default="vorp",
    )

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=12)

    def step_import():
        def _work():
            app.post("[1/3] 导入数据...")
            return DataIngestor().ingest_all()

        app.run_async(
            _work,
            on_done=lambda r: set_text(output, f"[完成] 导入完成：\n{r}"),
            status="导入中...",
        )

    def step_rank():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()

        def _work():
            app.post(f"[2/3] 计算 {method.upper()} 排名...")
            if method == "sgp":
                from ...core.sgp import SGPModel
                return SGPModel().generate_rankings()
            return ScoringModel().generate_rankings()

        app.run_async(
            _work,
            on_done=lambda r: set_text(output, f"[完成] 排名已保存：\n{r}"),
            status="计算排名中...",
        )

    def step_adp():
        def _work():
            app.post("【3/3】准备 ADP 数据…")
            cache = ADPCache()
            cache.fetch_adp(force=True)
            # adp_file 本身就是绝对路径（core/adp.py 内部已做 resolve_path）。
            # 修复：此前此处误调 resolve_path，而该名未导入 → 每次点击必弹 NameError。
            return cache.adp_file

        app.run_async(
            _work,
            on_done=lambda r: set_text(output, f"✅ ADP 已就绪：\n{r}"),
            status="准备 ADP…",
        )

    def run_full():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()

        def _work():
            app.post("[1/3] 导入数据...")
            DataIngestor().ingest_all()
            app.post("[2/3] 计算排名...")
            if method == "sgp":
                from ...core.sgp import SGPModel
                rank_path = SGPModel().generate_rankings()
            else:
                rank_path = ScoringModel().generate_rankings()
            app.post("[3/3] 准备 ADP...")
            ADPCache().fetch_adp(force=True)
            return rank_path

        app.run_async(
            _work,
            on_done=lambda r: set_text(output, f"[完成] 流水线完成！\n排名文件：{r}"),
            status="运行流水线...",
        )

    def show_rankings():
        """查看排名 Top 30：DB 快照优先，CSV 回退（兼容旧数据）。"""
        import pandas as pd
        method = method_var.get()
        value_col = "sgp_total" if method == "sgp" else "vorp"
        title = "SGP" if method == "sgp" else "VORP"

        df = None
        # 1. 数据库快照（rank 列在 DB 中统一命名）
        try:
            from ...db import RankingsRepository, db_session

            with db_session() as conn:
                df = RankingsRepository(conn).get_latest(method)
        except Exception:
            df = None
        source = "数据库"

        # 2. CSV 回退（旧数据）
        if df is None or df.empty:
            if method == "sgp":
                rank_file = f"fantasy_draft_rankings_sgp_{get_season()}.csv"
                rank_col_csv = "sgp_rank"
            else:
                rank_file = f"fantasy_draft_rankings_vorp_{get_season()}.csv"
                rank_col_csv = "rank"
            rank_path = find_output_file(rank_file)
            if not os.path.exists(rank_path):
                set_text(output, f"排名数据不存在（数据库与 {rank_file} 均无）。\n请先点击「生成排名」。")
                return
            df = pd.read_csv(rank_path)
            if "rank" not in df.columns:
                df = df.rename(columns={rank_col_csv: "rank"})
            source = "CSV"

        top = df.head(30)
        lines = [f"{title} 排名 Top 30（共 {len(df)} 人，来源：{source}）：\n", "-" * 65]
        for _, r in top.iterrows():
            lines.append(
                f"{int(r['rank']):>3}. {r['name']:<22} {r.get('pos',''):<5} "
                f"{value_col}={r.get(value_col, 0):>8.2f}"
            )
        set_text(output, "\n".join(lines))
        app.set_status(f"{title} 排名: {len(df)} 人")

    action_button(btn_frame, "导入数据", step_import)
    action_button(btn_frame, "生成排名", step_rank)
    action_button(btn_frame, "准备ADP", step_adp)
    action_button(btn_frame, "运行完整流水线", run_full)
    action_button(btn_frame, "查看排名", show_rankings)
