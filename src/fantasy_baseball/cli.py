"""命令行接口。

统一入口：``python -m fantasy_baseball <command>``。

子命令：
  ingest    导入数据（CSV → 数据库）
  rank      生成 VORP 排名
  adp       准备/刷新 ADP 数据
  draft     蛇形单次选秀模拟
  simulate  蒙特卡洛选秀模拟
  sleeper   Sleeper 推荐
  validate  阵容验证
  fa        FA 分析（更新池/推荐）
  gui       启动图形界面
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional


def _cmd_ingest(args) -> int:
    from .core import DataIngestor

    counts = DataIngestor().ingest_all()
    print(f"[完成] 数据导入：{counts}")
    return 0


def _cmd_fetch_projections(args) -> int:
    """从 FantasyPros 抓取真实预测数据并入库。"""
    from .config import get_season
    from .core import DataIngestor

    season = args.season or get_season()
    counts = DataIngestor().ingest_from_web(season=season)
    print(f"[完成] 从 FantasyPros 抓取预测数据（{season}赛季）：")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print("\n现在可以运行: python -m fantasy_baseball rank")
    return 0


def _cmd_roster(args) -> int:
    """管理用户阵容（user_roster 表）。"""
    import os
    import pandas as pd
    from .config import get_config, resolve_path
    from .db import RosterRepository, db_session

    action = args.roster_action

    if action == "import":
        path = resolve_path(args.file) if not os.path.isabs(args.file) else args.file
        if not os.path.exists(path):
            print(f"[错误] 文件不存在: {path}")
            return 1
        df = pd.read_csv(path)
        # 提取用户阵容
        if "team" in df.columns and "is_user_pick" in df.columns:
            user_df = df[df["is_user_pick"] == True]
        elif "team" in df.columns:
            user_df = df[df["team"] == args.pick]
        else:
            user_df = df
        rows = [
            {"name": r.get("name"), "team": r.get("team_name", r.get("team", "")),
             "pos": r.get("pos"), "status": "active"}
            for _, r in user_df.iterrows()
        ]
        with db_session() as conn:
            n = RosterRepository(conn).replace_all(rows)
        print(f"[完成] 导入 {n} 名球员到阵容")
        return 0

    if action == "show":
        with db_session() as conn:
            repo = RosterRepository(conn)
            n = repo.count()
            df = repo.get_roster()
        if n == 0:
            print("阵容为空。用 'roster import <文件>' 导入。")
            return 0
        slots = get_config()["league"]["roster_slots"]
        pos_counts = df["pos"].value_counts().to_dict() if "pos" in df.columns else {}
        print(f"当前阵容（{n} 人）：")
        print("-" * 40)
        for _, r in df.iterrows():
            print(f"  {r['pos']:<5} {r['name']}")
        print("\n位置填充：")
        for pos, req in slots.items():
            cur = pos_counts.get(pos, 0)
            mark = "[OK]" if cur >= req else "[缺]"
            print(f"  {mark} {pos}: {cur}/{req}")
        return 0

    if action == "clear":
        with db_session() as conn:
            RosterRepository(conn).clear()
        print("[完成] 阵容已清空")
        return 0

    if action == "add":
        with db_session() as conn:
            RosterRepository(conn).add_player({
                "name": args.name, "pos": args.pos, "team": args.team or ""
            })
        print(f"[完成] 已添加 {args.name} ({args.pos})")
        return 0

    if action == "remove":
        with db_session() as conn:
            ok = RosterRepository(conn).remove_player(args.name)
        print(f"[完成] 已删除 {args.name}" if ok else f"[未找到] {args.name} 不在阵容中")
        return 0 if ok else 1

    return 1


def _cmd_rank(args) -> int:
    """生成排名（VORP 或 SGP）。"""
    if args.method == "sgp":
        from .core.sgp import SGPModel
        path = SGPModel().generate_rankings()
        print(f"[完成] SGP 排名已生成并写入数据库：{path}")
    else:
        from .core import ScoringModel
        path = ScoringModel().generate_rankings()
        print(f"[完成] VORP 排名已生成并写入数据库：{path}")
    print("时间戳历史备份：output/history/")
    return 0


def _cmd_adp(args) -> int:
    from .core import ADPCache

    cache = ADPCache()
    df = cache.fetch_adp(force=args.force)
    _src_text = {
        "network": "网络抓取，已写入数据库",
        "db": "数据库缓存",
        "csv_legacy": "根目录 adp.csv 缓存",
        "csv_latest": "最近一份 CSV 备份",
        "mock": "示例数据（网络不可用，未写库）",
    }
    print(f"[完成] ADP 数据就绪（{len(df)} 条，来源：{_src_text.get(cache.last_source, cache.last_source)}）")
    return 0


def _cmd_standings(args) -> int:
    """F1 模拟战绩榜：SGP 投影用户阵容。"""
    from .core.standings import ProjectedStandings
    from .db import RosterRepository, db_session

    with db_session() as conn:
        roster = RosterRepository(conn).get_roster()
    if roster.empty:
        print("[错误] 阵容为空。先导入阵容：roster import <日志> 或 GUI「从最近模拟导入」")
        return 1

    result = ProjectedStandings().project(roster)
    print(f"模拟战绩榜（联盟 {result['league_size']} 队，阵容相对平均队总 SGP："
          f"{result['total_sgp']:+.2f}，总榜期望名次 {result['exp_total_rank']:.1f}）")
    print("-" * 62)
    print(f"{'类别':<6} {'你的队':>10} {'平均队':>10} {'SGP':>8} {'期望名次':>8}")
    for r in result["categories"]:
        rank_txt = f"{r['exp_rank']:.1f}" if r["exp_rank"] is not None else "—"
        print(f"{r['category']:<6} {r['team_value']:>10} {r['league_avg']:>10} "
              f"{r['sgp']:>+8.2f} {rank_txt:>8}")
    print("\n说明：其他球队为统计模拟（P4a 接入后可用真实联盟数据）；"
          "SGP 正=高于平均。")
    return 0


def _cmd_draft(args) -> int:
    from .core import SnakeDraftSimulator

    path = SnakeDraftSimulator(method=getattr(args, "method", "vorp")).simulate_and_save(
        user_pick=args.pick, strategy=args.strategy
    )
    print(f"[完成] 选秀日志已写入数据库（会话保存）：{path}")
    print("提示：roster import 可直接用该 CSV，或用 GUI「从最近模拟导入」读库")
    return 0


def _cmd_simulate(args) -> int:
    from .core import DraftEngine

    method = getattr(args, "method", "vorp")
    engine = DraftEngine(method=method)
    avail = engine.analyze_availability(target_pick=args.user_pick)
    threshold = args.min_availability
    top = avail[avail["availability_prob"] >= threshold].head(15)
    if top.empty:
        print(f"在可用率 >= {threshold} 时无目标球员，尝试降低 --min-availability")
        return 1
    value_col = "sgp_total" if method == "sgp" else "vorp"
    value_label = "SGP" if method == "sgp" else "VORP"
    print(f"第{args.user_pick}顺位高可用目标（可用率 >= {threshold}）：")
    print("-" * 60)
    for _, r in top.iterrows():
        print(
            f"{r['name']:<25} 可用率={r['availability_prob']*100:5.1f}%  "
            f"{value_label}={r[value_col]:6.1f}  ADP={r['adp']}"
        )
    return 0


def _cmd_sleeper(args) -> int:
    from .core import find_sleepers

    df = find_sleepers(
        min_adp=args.min_adp,
        max_adp=args.max_adp,
        min_bias=args.min_bias,
        top=args.top,
        position=None if args.position == "All" else args.position,
        use_statcast=not args.no_statcast,
    )
    if df.empty:
        print("未找到符合条件的 Sleeper 球员。")
        return 1
    print(f"发现 {len(df)} 个 Sleeper 候选：")
    print("-" * 60)
    for _, r in df.iterrows():
        sc = f" [Statcast: {r['statcast_signal']}]" if r.get("statcast_signal") else ""
        print(f"{r['name']} ({r.get('pos', '')})  ADP={r['adp']}  偏差={r['bias']}{sc}")
    return 0


def _cmd_validate(args) -> int:
    from .core import RosterValidator

    v = RosterValidator()
    result = v.validate_roster(args.draft_log, team_id=args.team)
    print("阵容合规性检查：")
    print("-" * 50)
    for pos, required in result.slot_requirements.items():
        cur = result.pos_counts.get(pos, 0)
        mark = "[OK]" if cur == required else ("[缺]" if cur < required else "[超]")
        print(f"{mark} {pos}: {cur}/{required}")
    if result.suggestions:
        print("\n建议：")
        for s in result.suggestions:
            print(f"  - {s}")
    print("\n" + ("阵容合规！" if result.is_valid else "阵容需要调整"))

    if args.analyze:
        strength = v.analyze_roster_strength(args.draft_log, team_id=args.team)
        if strength:
            print("\n阵容强度：")
            print("-" * 50)
            print(f"总 VORP: {strength.total_vorp:.2f}")
            print(f"平均 VORP: {strength.avg_vorp:.2f}")
    return 0 if result.is_valid else 1


def _cmd_fa(args) -> int:
    from .fa import FAAnalyzer, RealTimeData, RecommendationSystem

    if args.action == "update-fa":
        RealTimeData().update_fa_pool()
        print("[完成] FA 池已更新（内置示例数据）")
        return 0
    if args.action == "update-injury":
        injuries = RealTimeData().update_injury_data(days_back=args.days_back)
        print(f"[完成] 伤病数据已更新（{len(injuries)} 条，回溯 {args.days_back} 天）")
        return 0
    if args.action == "import-pool":
        # 修复审计项：不带 --file 时曾对项目根目录 read_csv 抛原始异常
        import os
        from .config import resolve_path
        file_path = args.file if os.path.isabs(args.file) else resolve_path(args.file)
        if not args.file or not os.path.isfile(file_path):
            print(f"[错误] 请指定有效的 CSV 文件：fa import-pool <file>")
            print("CSV 格式：player_id,name,team,pos,status")
            return 1
        n = RealTimeData().import_data_from_file(args.file, "fa_pool")
        if n == 0:
            print("[错误] 导入失败：文件不存在或格式不正确")
            print("CSV 格式：player_id,name,team,pos,status")
            return 1
        print(f"[完成] 导入 {n} 名 FA 球员")
        return 0
    if args.action == "show-pool":
        import pandas as pd
        from .db import FaRepository, db_session
        with db_session() as conn:
            df = FaRepository(conn).get_pool()
        if df.empty:
            print("FA 池为空。用 'fa update-fa' 或 'fa import-pool <file>' 添加。")
            return 0
        print(f"当前 FA 池（{len(df)} 人）：")
        print("-" * 40)
        for _, r in df.iterrows():
            print(f"  {r.get('pos','?'):<5} {r['name']}")
        return 0
    # recommend
    analyzer = FAAnalyzer(method=getattr(args, "method", "vorp"))
    rec = RecommendationSystem(analyzer)
    position = None if args.position == "All" else args.position
    result = rec.generate_recommendations(
        position=position, top_n=args.top, risk_preference=args.risk
    )
    if not result:
        print("未生成推荐，请先运行 fa update-fa。")
        return 1
    print(f"FA 推荐（{args.risk}策略，Top {len(result)}）：")
    print("-" * 60)
    for i, r in enumerate(result, 1):
        print(
            f"{i}. {r['name']} ({r['pos']})  得分={r['final_score']:.1f}  "
            f"价值={r['value']['overall_value']:.1f}"
        )
    return 0


def _cmd_gui(args) -> int:
    from .gui import run_gui

    run_gui()
    return 0


def _cmd_mlb(args) -> int:
    """查询 MLB 球员真实统计与 Statcast。"""
    from .data_fetch import MLBStatsClient, StatcastFetcher

    client = MLBStatsClient()
    person = client.search_player(args.name)
    if not person:
        print(f"[未找到] 找不到球员：{args.name}")
        return 1

    mlb_id = person["id"]
    name = person.get("fullName", args.name)
    pos = person.get("primaryPosition", {}).get("abbreviation", "?")
    # 修复 M10：默认当前年（修复前硬编码 2025）
    import datetime
    season = args.season or datetime.datetime.now().year

    print(f"\n{name} ({pos}) | MLB id={mlb_id} | {season}赛季")
    print("=" * 50)

    stats = client.fetch_player_stats(mlb_id, season)
    if stats and stats.get("stats"):
        print("\n[赛季统计]")
        for k, v in stats["stats"].items():
            if v is not None:
                print(f"  {k:<12}: {v}")
    else:
        print("\n[赛季统计] 无数据")

    if args.statcast:
        print("\n[Statcast]")
        fetcher = StatcastFetcher()
        sc = (
            fetcher.fetch_pitcher_data(mlb_id, season)
            if pos in ("P", "TWP")
            else fetcher.fetch_hitter_data(mlb_id, season)
        )
        if sc:
            for k, v in sc.items():
                print(f"  {k:<22}: {v}")
        else:
            print("  无数据")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy_baseball",
        description="Fantasy Baseball Pro — 分析与选秀模拟系统",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # ingest
    p = sub.add_parser("ingest", help="从本地 CSV 导入数据")
    p.set_defaults(func=_cmd_ingest)

    # fetch-projections
    p = sub.add_parser("fetch-projections", help="从 FantasyPros 抓取真实预测数据")
    p.add_argument("--season", type=int, default=None, help="赛季年份（默认当前年）")
    p.set_defaults(func=_cmd_fetch_projections)

    # rank
    p = sub.add_parser("rank", help="生成排名（VORP 或 SGP）")
    p.add_argument("--method", default="vorp", choices=["vorp", "sgp"],
                   help="评分方法：vorp（默认，线性加权）或 sgp（5×5 类别）")
    p.set_defaults(func=_cmd_rank)

    # adp
    p = sub.add_parser("adp", help="准备 ADP 数据")
    p.add_argument("--force", action="store_true", help="强制刷新")
    p.set_defaults(func=_cmd_adp)

    # draft
    p = sub.add_parser("draft", help="蛇形选秀模拟")
    p.add_argument("--pick", type=int, default=5, help="选秀顺位（默认5）")
    p.add_argument(
        "--strategy", default="balanced",
        choices=["balanced", "conservative", "aggressive"],
    )
    p.add_argument("--method", default="vorp", choices=["vorp", "sgp"],
                   help="评分方法：vorp（默认）或 sgp")
    p.set_defaults(func=_cmd_draft)

    # simulate
    p = sub.add_parser("simulate", help="蒙特卡洛选秀模拟")
    p.add_argument("--user-pick", type=int, default=5, help="你的顺位")
    p.add_argument("--min-availability", type=float, default=0.25, help="最小可用率阈值")
    p.add_argument("--method", default="vorp", choices=["vorp", "sgp"],
                   help="评分方法：vorp（默认）或 sgp")
    p.set_defaults(func=_cmd_simulate)

    # standings（F1 模拟战绩榜）
    p = sub.add_parser("standings", help="模拟战绩榜（SGP 投影，需已导入阵容）")
    p.set_defaults(func=_cmd_standings)

    # sleeper
    p = sub.add_parser("sleeper", help="Sleeper 推荐")
    p.add_argument("--min-adp", type=int, default=80)
    p.add_argument("--max-adp", type=int, default=300)
    p.add_argument("--min-bias", type=int, default=30)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--position", default="All")
    p.add_argument("--no-statcast", action="store_true", help="禁用 Statcast 增强")
    p.set_defaults(func=_cmd_sleeper)

    # validate
    p = sub.add_parser("validate", help="阵容验证")
    p.add_argument("draft_log", help="选秀日志文件路径")
    p.add_argument("--analyze", action="store_true", help="分析阵容强度")
    p.add_argument("--team", type=int, default=None,
                   help="你的球队编号（日志无 is_user_pick 列时用于过滤；默认自动识别）")
    p.set_defaults(func=_cmd_validate)

    # roster
    p = sub.add_parser("roster", help="管理用户阵容")
    p_sub = p.add_subparsers(dest="roster_action", required=True)
    p_imp = p_sub.add_parser("import", help="从选秀日志导入阵容")
    p_imp.add_argument("file", help="选秀日志 CSV 路径")
    p_imp.add_argument("--pick", type=int, default=5, help="你的顺位（无 is_user_pick 列时用）")
    p_sub.add_parser("show", help="查看当前阵容")
    p_sub.add_parser("clear", help="清空阵容")
    p_add = p_sub.add_parser("add", help="添加球员")
    p_add.add_argument("name", help="球员姓名")
    p_add.add_argument("--pos", required=True, help="位置")
    p_add.add_argument("--team", default="", help="球队")
    p_rm = p_sub.add_parser("remove", help="删除球员")
    p_rm.add_argument("name", help="球员姓名")
    p.set_defaults(func=_cmd_roster)

    # fa
    p = sub.add_parser("fa", help="FA 分析")
    p.add_argument(
        "action",
        choices=["update-fa", "update-injury", "recommend", "import-pool", "show-pool"],
        help="操作",
    )
    p.add_argument("--file", default="", help="CSV 文件路径（import-pool 用）")
    p.add_argument("--position", default="All")
    p.add_argument("--risk", default="balanced", choices=["balanced", "conservative", "aggressive"])
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--method", default="vorp", choices=["vorp", "sgp"],
                   help="评分方法（recommend 用）")
    p.add_argument("--days-back", type=int, default=30, help="伤病回溯天数（update-injury 用）")
    p.set_defaults(func=_cmd_fa)

    # mlb
    p = sub.add_parser("mlb", help="查询 MLB 球员真实统计")
    p.add_argument("name", help="球员姓名（如 'Shohei Ohtani'）")
    p.add_argument("--season", type=int, default=None,
                   help="赛季年份（默认当前年）")
    p.add_argument("--statcast", action="store_true", help="同时显示 Statcast")
    p.set_defaults(func=_cmd_mlb)

    # gui
    p = sub.add_parser("gui", help="启动图形界面")
    p.set_defaults(func=_cmd_gui)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        # 无子命令时默认启动 GUI
        try:
            from .gui import run_gui
            run_gui()
            return 0
        except Exception as e:
            print(f"GUI 启动失败：{e}\n请使用 --help 查看命令行子命令。", file=sys.stderr)
            return 1

    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        # 审计低危项：此前业务异常（如伤病抓取断网）以裸 traceback 冒出
        print(f"[错误] {e}", file=sys.stderr)
        return 1
