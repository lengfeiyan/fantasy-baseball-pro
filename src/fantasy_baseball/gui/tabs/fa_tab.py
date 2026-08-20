"""FA 分析选项卡：自由球员推荐。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...fa import FAAnalyzer, RealTimeData, RecommendationSystem
from ..errors import friendly_error
from ._widgets import (
    action_button,
    labeled_combobox,
    labeled_input,
    section_frame,
    set_text,
    text_display,
)


def create_tab(parent: tk.Widget, app) -> None:
    # 输出区先创建（更新按钮需要引用它）
    _, output = text_display(parent, height=14)

    # 数据更新
    update_frame = section_frame(parent, "数据更新")
    ttk.Button(
        update_frame, text="更新FA池(内置)", command=lambda: _update(app, output, "fa")
    ).pack(side=tk.LEFT, padx=4)
    ttk.Button(
        update_frame, text="更新伤病", command=lambda: _update(app, output, "injury")
    ).pack(side=tk.LEFT, padx=4)
    ttk.Button(
        update_frame, text="导入FA池CSV", command=lambda: _import_fa_csv(app, output)
    ).pack(side=tk.LEFT, padx=4)
    ttk.Button(
        update_frame, text="查看FA池", command=lambda: _show_fa_pool(app, output)
    ).pack(side=tk.LEFT, padx=4)

    # 推荐参数
    param_frame = section_frame(parent, "推荐参数")
    _, method_var = labeled_combobox(
        param_frame, "评分方法", ["vorp", "sgp"], default="vorp",
    )
    _, pos_var = labeled_combobox(
        param_frame,
        "位置筛选",
        ["All", "C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "UTIL"],
        default="All",
    )
    _, risk_var = labeled_combobox(
        param_frame, "风险偏好", ["balanced", "conservative", "aggressive"], default="balanced"
    )
    _, top_var = labeled_input(param_frame, "推荐数量", "10")

    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=8)

    def do_recommend():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()
        pos_sel = pos_var.get()
        top_s = top_var.get()
        risk = risk_var.get()

        def _work():
            app.post(f"生成 FA 推荐中（{method.upper()}）...")
            analyzer = FAAnalyzer(method=method)
            rec = RecommendationSystem(analyzer)
            position = None if pos_sel == "All" else pos_sel
            result = rec.generate_recommendations(
                position=position, top_n=int(top_s), risk_preference=risk,
                cancel_check=app.is_cancelled,
            )
            if not result:
                if app.is_cancelled():
                    from ..app import TaskCancelled
                    raise TaskCancelled()
                return "未生成推荐，请先更新 FA 池。"

            # 检查阵容是否设置 + 显示缺口
            from ...db import RosterRepository, db_session
            from ...config import get_config
            with db_session() as conn:
                repo = RosterRepository(conn)
                roster_count = repo.count()
                roster_df = repo.get_roster()

            lines = [f"FA 推荐（{risk}策略，Top {len(result)}）：\n", "-" * 60 + "\n"]
            if roster_count == 0:
                lines.append("[提示] 阵容未设置，推荐基于空阵容（所有位置都缺）。\n")
                lines.append("去「阵容验证」选项卡导入阵容后，推荐会优先填补缺口位置。\n")
            else:
                # 显示阵容缺口
                slots = get_config()["league"]["roster_slots"]
                pos_counts = roster_df["pos"].value_counts().to_dict() if "pos" in roster_df.columns else {}
                missing = []
                for pos, required in slots.items():
                    cur = pos_counts.get(pos, 0)
                    if cur < required:
                        missing.append(f"{pos}({cur}/{required})")
                if missing:
                    lines.append(f"[阵容缺口] 需补: {', '.join(missing)}\n")
                else:
                    lines.append("[阵容已满] 按综合价值排序推荐\n")

            for i, r in enumerate(result, 1):
                mock_mark = "（示例数据）" if r.get("is_mock") else ""
                lines.append(
                    f"{i}. {r['name']}{mock_mark} ({r['pos']})  得分={r['final_score']:.1f}  "
                    f"价值={r['value']['overall_value']:.1f}  需求={r['need_factor']:.2f}"
                )
            return "\n".join(lines)

        app.run_async(_work, on_done=lambda r: set_text(output, r), status="生成推荐...")

    def do_export():
        # UI 线程先取值（Tk 变量不支持跨线程访问）
        method = method_var.get()
        pos_sel = pos_var.get()
        top_s = top_var.get()
        risk = risk_var.get()

        def _work():
            analyzer = FAAnalyzer(method=method)
            rec = RecommendationSystem(analyzer)
            position = None if pos_sel == "All" else pos_sel
            result = rec.generate_recommendations(
                position=position, top_n=int(top_s), risk_preference=risk
            )
            if not result:
                return None
            return rec.export_recommendations(
                result, "fa_recommendations.csv",
                method=method, risk_preference=risk,
            )

        def _done(path):
            if path:
                set_text(
                    output,
                    "[完成] 推荐已写入数据库（会话保存）\n"
                    f"最近一份 CSV：{path}\n"
                    "历史备份：output/history/（时间戳文件）",
                )
            else:
                set_text(output, "无可导出的推荐。")

        app.run_async(_work, on_done=_done, status="导出中...")

    action_button(btn_frame, "生成推荐", do_recommend)
    action_button(btn_frame, "导出结果", do_export)


def _update(app, output, kind):
    def _work():
        rtd = RealTimeData()
        if kind == "fa":
            rtd.update_fa_pool()
            return "FA 池已更新（内置示例数据）"
        injuries = rtd.update_injury_data()
        if not injuries:
            return "该时段无伤病动态（0 条），数据库保留原有数据"
        return f"伤病数据已更新（{len(injuries)} 条）"

    app.run_async(_work, on_done=lambda r: set_text(output, f"[完成] {r}"), status="更新中...")


def _import_fa_csv(app, output):
    """从 CSV 导入用户联盟的真实 FA 池。"""
    from tkinter import filedialog, messagebox

    path = filedialog.askopenfilename(
        title="选择 FA 池 CSV 文件",
        filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")],
    )
    if not path:
        return

    def _work():
        from ...config import resolve_path
        rtd = RealTimeData()
        n = rtd.import_data_from_file(path, "fa_pool")
        if n == 0:
            raise ValueError("导入失败：文件为空或格式不正确")
        return n

    def _done(n):
        set_text(output, (
            f"[完成] 已导入 {n} 名 FA 球员\n\n"
            f"CSV 格式要求：\n"
            f"  player_id,name,team,pos,status\n"
            f"  （player_id 可留空，name/pos 为必需）\n\n"
            f"现在可以生成推荐，会基于你的真实 FA 池。"
        ))
        messagebox.showinfo("成功", f"导入 {n} 名 FA 球员")

    def _error(e):
        messagebox.showerror("错误", friendly_error(e))

    app.run_async(_work, on_done=_done, on_error=_error, status="导入FA池...")


def _show_fa_pool(app, output):
    """查看当前 FA 池。"""
    from ...db import FaRepository, db_session

    with db_session() as conn:
        df = FaRepository(conn).get_pool()

    if df.empty:
        set_text(output, "FA 池为空。点击「更新FA池」用内置数据，或「导入FA池CSV」用你联盟的数据。")
        return

    lines = [f"当前 FA 池（{len(df)} 人）：\n", "-" * 50]
    for _, r in df.iterrows():
        lines.append(f"  {r.get('pos','?'):<5} {r['name']:<25} {r.get('team','')}")
    set_text(output, "\n".join(lines))
    app.set_status(f"FA池: {len(df)} 人")
