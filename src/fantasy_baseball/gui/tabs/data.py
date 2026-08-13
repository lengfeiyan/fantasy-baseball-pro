"""数据管理选项卡：导入预测数据（网络/CSV）与查看状态。

两种数据来源：
- 网络：从 FantasyPros 自动抓取真实预测（推荐，含 800+ 球员）
- CSV：手动导入本地文件（离线备选）
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import DataIngestor
from ...db import PlayerRepository, db_session
from ._widgets import action_button, labeled_input, section_frame, set_text, text_display


def create_tab(parent: tk.Widget, app) -> None:
    # 网络获取区
    web_frame = section_frame(parent, "从网络获取预测数据（推荐）")
    ttk.Label(
        web_frame,
        text=(
            "从 FantasyPros 自动抓取真实预测数据（聚合 Steamer/ZiPS/THE BAT X/ATC），\n"
            "含 800+ 打者 + 900+ 投手，同时自动填充位置映射。无需手动下载 CSV。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W)
    _, season_var = labeled_input(web_frame, "赛季", "2026", width=8)

    # CSV 导入区
    csv_frame = section_frame(parent, "从本地 CSV 导入（离线备选）")
    ttk.Label(
        csv_frame,
        text=(
            "把 CSV 放到 data/ 目录（文件名遵循 config.yaml 配置）：\n"
            "  data/hitters_2026_steamer.csv / data/pitchers_2026_steamer.csv\n"
            "  data/player_positions_2025.csv（位置映射，网络获取时不需要）"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W)

    # 操作按钮
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)
    _, output = text_display(parent, height=10)

    def do_fetch_web():
        def _work():
            season = int(season_var.get())
            app.post(f"从 FantasyPros 抓取 {season} 赛季预测数据...")
            counts = DataIngestor().ingest_from_web(season=season)
            return counts

        def _done(result):
            lines = ["[完成] 网络预测数据导入成功：\n"]
            for k, v in result.items():
                lines.append(f"  {k}: {v}")
            lines.append("\n现在可以在「分析流水线」生成排名，或直接选秀模拟。")
            set_text(output, "\n".join(lines))
            app.set_status("预测数据导入完成")

        app.run_async(_work, on_done=_done, status="抓取预测数据中...")

    def do_ingest_csv():
        def _work():
            app.post("从本地 CSV 导入数据...")
            counts = DataIngestor().ingest_all()
            return counts

        def _done(result):
            set_text(output, f"[完成] CSV 导入成功：\n{result}")
            app.set_status("CSV 导入完成")

        app.run_async(_work, on_done=_done, status="CSV 导入中...")

    def do_status():
        with db_session() as conn:
            counts = PlayerRepository(conn).count()
        set_text(output, f"当前数据库各表行数：\n{counts}")
        app.set_status("已刷新")

    action_button(btn_frame, "网络获取预测", do_fetch_web)
    action_button(btn_frame, "CSV导入", do_ingest_csv)
    action_button(btn_frame, "查看状态", do_status)
