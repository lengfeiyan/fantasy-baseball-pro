"""阵容验证与管理选项卡。

两个功能区：
- 阵容验证：检查选秀日志 CSV 的合规性
- 我的阵容：把阵容存入数据库（user_roster 表），让 FA 推荐基于真实阵容需求
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...config import get_config
from ...core import RosterValidator
from ...db import RosterRepository, db_session
from ._widgets import (
    action_button,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    # ===== 阵容验证区（原有功能）=====
    file_frame = section_frame(parent, "阵容验证（选秀日志 CSV）")
    _, log_var = labeled_input(file_frame, "日志文件", "draft_log_pick5_balanced.csv", width=40)

    def browse():
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            log_var.set(path)

    ttk.Button(file_frame, text="浏览...", command=browse).pack(side=tk.LEFT, padx=4)

    btn_validate_frame = ttk.Frame(parent)
    btn_validate_frame.pack(pady=4)

    _, output = text_display(parent, height=14)

    def do_validate():
        def _work():
            app.post("验证阵容中...")
            v = RosterValidator()
            result = v.validate_roster(log_var.get())
            strength = v.analyze_roster_strength(log_var.get())

            lines = ["阵容合规性检查\n", "-" * 50 + "\n"]
            for pos, required in result.slot_requirements.items():
                cur = result.pos_counts.get(pos, 0)
                mark = "[OK]" if cur == required else ("[缺]" if cur < required else "[超]")
                lines.append(f"{mark} {pos}: {cur}/{required}")
            lines.append("\n" + ("阵容合规！" if result.is_valid else "阵容需要调整"))

            if result.suggestions:
                lines.append("\n建议：")
                for s in result.suggestions:
                    lines.append(f"  - {s}")

            if strength:
                lines.append("\n阵容强度")
                lines.append("-" * 50)
                lines.append(f"总 VORP: {strength.total_vorp:.2f}")
                lines.append(f"平均 VORP: {strength.avg_vorp:.2f}")
                if strength.hitter_pitcher_ratio is not None:
                    ratio = f"{strength.hitter_pitcher_ratio:.2f} : 1"
                else:
                    ratio = "投手为0，无法计算"
                lines.append(f"打者/投手比例: {ratio}")
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="验证阵容...")

    action_button(btn_validate_frame, "验证阵容", do_validate)

    # ===== 我的阵容管理区 =====
    roster_frame = section_frame(parent, "我的阵容（FA 推荐会基于此分析位置需求）")
    ttk.Label(
        roster_frame,
        text=(
            "把阵容保存到数据库后，FA 分析的推荐会优先填补你缺少的位置。\n"
            "推荐流程：先在「选秀模拟」模拟选秀 → 回到这里 → 「从选秀日志导入」阵容。"
        ),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=2)
    # 顺位输入（修复 M1：之前硬编码第 5 顺位）
    _, pick_var = labeled_input(roster_frame, "你的顺位", "5", width=5)

    btn_roster_frame = ttk.Frame(roster_frame)
    btn_roster_frame.pack(pady=4)

    def do_import():
        """从选秀日志 CSV 导入阵容到 user_roster 表。"""
        log_path = log_var.get().strip()
        if not log_path:
            messagebox.showwarning("提示", "请先填写选秀日志文件路径")
            return

        def _work():
            app.post("从选秀日志导入阵容...")
            import os
            from ...config import find_output_file
            path = find_output_file(log_path)
            if not os.path.exists(path):
                raise FileNotFoundError(f"文件不存在: {path}")

            import pandas as pd
            df = pd.read_csv(path)

            # 尝试提取用户阵容（draft log 有 is_user_pick 列时优先用之；否则按顺位）
            user_pick = int(pick_var.get())
            if "team" in df.columns and "is_user_pick" in df.columns:
                user_df = df[df["is_user_pick"] == True]
            elif "team" in df.columns:
                user_df = df[df["team"] == user_pick]
            else:
                user_df = df

            rows = []
            for _, r in user_df.iterrows():
                rows.append({
                    "name": r.get("name"),
                    "team": r.get("team_name", r.get("team", "")),
                    "pos": r.get("pos"),
                    "status": "active",
                })

            with db_session() as conn:
                n = RosterRepository(conn).replace_all(rows)
            return n

        def _done(n):
            set_text(output, f"[完成] 已导入 {n} 名球员到阵容\n点击「查看阵容」确认。")
            app.set_status("阵容导入完成")
            messagebox.showinfo("成功", f"已导入 {n} 名球员")

        def _error(e):
            messagebox.showerror("错误", str(e))

        app.run_async(_work, on_done=_done, on_error=_error, status="导入阵容...")

    def do_show():
        """查看当前阵容 + 位置填充状态。"""
        with db_session() as conn:
            repo = RosterRepository(conn)
            n = repo.count()
            df = repo.get_roster()

        cfg = get_config()
        slots = cfg["league"]["roster_slots"]

        if n == 0:
            lines = ["阵容为空。请先从选秀日志导入。\n"]
            lines.append("所有位置都缺人，FA 推荐会认为你什么都缺。")
            set_text(output, "\n".join(lines))
            return

        lines = [f"当前阵容（{n} 人）：\n", "-" * 50]
        for _, r in df.iterrows():
            lines.append(f"  {r['pos']:<5} {r['name']}")

        # 位置填充状态
        pos_counts = df["pos"].value_counts().to_dict() if "pos" in df.columns else {}
        lines.append("\n位置填充状态：")
        for pos, required in slots.items():
            cur = pos_counts.get(pos, 0)
            mark = "[OK]" if cur >= required else "[缺]"
            lines.append(f"  {mark} {pos}: {cur}/{required}")

        missing = [p for p, req in slots.items() if pos_counts.get(p, 0) < req]
        if missing:
            lines.append(f"\n缺口位置: {', '.join(missing)}")
            lines.append("FA 推荐会优先推荐这些位置的球员。")
        else:
            lines.append("\n阵容已满，FA 推荐按综合价值排序。")

        set_text(output, "\n".join(lines))
        app.set_status(f"阵容: {n} 人")

    def do_clear():
        if not messagebox.askyesno("确认", "确定清空阵容？"):
            return
        with db_session() as conn:
            RosterRepository(conn).clear()
        set_text(output, "阵容已清空。")
        app.set_status("阵容已清空")

    action_button(btn_roster_frame, "从选秀日志导入", do_import)
    action_button(btn_roster_frame, "查看阵容", do_show)
    action_button(btn_roster_frame, "清空阵容", do_clear)
