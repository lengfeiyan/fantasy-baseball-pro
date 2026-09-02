"""新秀雷达（Rookie Radar，F7）。

面向 redraft 联盟的选秀 sleeper 榜：从 MLB Pipeline 天赋榜出发，融合
Statcast 高阶数据，回答"明年开季谁就能出数据、且 ADP 还便宜"。

四层数据模型（高层覆盖低层，逐行标注 tier，不静默降质）：
- A：MLB Statcast 百分位（复用 S1/S2 的 SavantLeaderboard）——已登板的板上有幸存者
- B：MiLB Statcast 聚合（EV/whiff/woba against，仅 AAA 与 Single-A 有公开 tracking）
- C：Pipeline 内嵌当季统计的比率类（K%/BB%，MLB 已算好），全员兜底（含 AA 盲区）
- D：MLB 春训聚合（game_type=S）——选秀窗口才新鲜，由调用方显式启用
  优先级 A > B > D > C；易注水的 MiLB 计数类（HR/RBI 总量）不进任何因子。

接近度（proximity）：优先用现属球队精确归因（people 批量 currentTeam +
球队级别映射，含 9 月升班等标记滞后的真实证据）；归因不可用时退回启发式
（levels 标记 + 年龄 + MiLB Statcast 索引证据，Pipeline 页面无 ETA 字段）。
分 已登板/近/中/远，默认剔除"远"。

红线：本模块不写回 VORP/SGP 核心评分；综合分只用于雷达榜排序与
可开关的新秀加成标签（config fa_analyzer.rookie_boost，默认关）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import get_season
from ..data_fetch.milb_statcast import MilbStatcastFetcher
from ..data_fetch.pipeline import PipelineFetcher
from ..utils.logger import get_logger

logger = get_logger("rookies")

# 接近度分档与分值（加权用；"远"仅 --all 时保留）
_PROXIMITY_ORDER = ("已登板", "近", "中", "远")
_PROXIMITY_SCORE = {"已登板": 1.0, "近": 0.7, "中": 0.4, "远": 0.1}
_DEFAULT_KEEP = ("已登板", "近", "中")

# 综合分权重（模块常量而非 config：口径变更应伴随测试与文档同步，不走静默配置）
_W_TALENT = 0.45     # Pipeline 排名先验（主权重）
_W_METRIC = 0.25     # 当前层级高阶指标
_W_PROXIMITY = 0.20  # 接近度
_W_VALUE = 0.10      # ADP 价值差

# value_gap（adp_rank − pipeline_rank）截断区间：>0 = 市场低估
_GAP_CLIP_LOW, _GAP_CLIP_HIGH = -50, 200

_HITTER_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "CF", "LF", "RF", "DH", "UTIL"}


def _num(v) -> Optional[float]:
    """值转 float；None/NaN/不可解析返回 None。"""
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _name_key(name: str) -> str:
    return " ".join(str(name or "").split()).casefold()


def compute_proximity(prospect: Dict[str, Any],
                      milb_index: Dict[int, Dict[str, Any]],
                      resolved_level: Optional[str] = None) -> str:
    """接近度：现属级别精确归因优先，未归因时退回启发式。

    Args:
        prospect: normalize_prospect 输出行
        milb_index: MiLB Statcast 聚合索引（mlb_id → stats）。索引本身不带
            级别（服务端忽略 level 过滤，见 milb_statcast docstring），
            "在索引中"仅作为"本赛季到过有 tracking 的级别（AAA/Single-A）"证据
        resolved_level: 现属球队归因的级别标签（MLB/AAA/AA/A+/A/ROK），
            来自 people 批量 currentTeam + 球队级别映射；None = 未归因
    """
    levels = str(prospect.get("levels") or "")
    top = str(prospect.get("top_level") or "")
    age = _num(prospect.get("age")) or 99
    tracked_hit = prospect.get("mlb_id") in milb_index

    # 精确归因优先：现属球队是最真实的级别证据（含 9 月升班这类
    # Pipeline 标记滞后/缺失的场景）
    if resolved_level is not None:
        if resolved_level == "MLB":
            return "已登板"
        if resolved_level in ("AAA", "AA"):
            return "近"
        if resolved_level == "A+":
            return "中"
        return "远"  # A / ROK

    # 启发式兜底（级别归因不可用时）
    if "MLB" in levels.upper():
        return "已登板"
    if "AAA" in levels:
        return "近"
    if "AA" in levels.replace("AAA", ""):
        return "近"
    if top == "MULTI":
        # 多级跳动的快速晋升者：成年组视为近，未成年视为中
        return "近" if age >= 20 else "中"
    if top == "A+":
        return "中"
    if tracked_hit and age >= 20:
        # 无级别标记但确有 AAA/Single-A tracking 记录的成年球员，保守视为近
        return "近"
    return "远"


class RookieRadar:
    """新秀雷达主计算器。"""

    def __init__(self,
                 pipeline_fetcher: Optional[PipelineFetcher] = None,
                 milb_fetcher: Optional[MilbStatcastFetcher] = None,
                 adp_df: Optional[pd.DataFrame] = None,
                 stats_client=None,
                 deep_adp: bool = True):
        """
        Args:
            stats_client: MLBStatsClient 实例——级别归因（批量 currentTeam +
                球队级别映射）依赖它；None 则跳过归因，接近度退回启发式（测试用）
            deep_adp: 是否用 deep ADP（overall+位置页并集）补充主 ADP 覆盖
        """
        self._pipeline = pipeline_fetcher
        self._milb = milb_fetcher
        self._adp_df = adp_df
        self._stats_client = stats_client
        self._deep_adp_enabled = deep_adp

    # -------------------------------------------------------------- 主流程
    def build(self, include_far: bool = False, use_spring: bool = False,
              season: Optional[int] = None, force: bool = False) -> pd.DataFrame:
        """生成新秀雷达榜。

        Args:
            include_far: 保留"远"接近度（默认剔除，redraft 用不上）
            use_spring: 启用春训数据（Tier D，选秀窗口才用）
            season: 目标赛季（默认 config season；榜单与统计均为当前数据）
            force: 强刷各数据源缓存
        Returns:
            按 composite 降序的 DataFrame（空榜返回空表）。
        Raises:
            RuntimeError: Pipeline 榜单抓取失败（网络/页面变更）——与"空榜"区分。
        """
        season = season or get_season()
        pipeline = self._pipeline or PipelineFetcher()
        board = pipeline.fetch_top_prospects(season=season, force=force)
        if board is None:
            raise RuntimeError(
                "Pipeline 榜单抓取失败（网络不可用或页面结构变更）。"
                "雷达需要榜单先验数据，请联网后重试。"
            )
        if not board:
            logger.warning("Pipeline 榜单为空")
            return pd.DataFrame()

        milb = self._milb or MilbStatcastFetcher()
        milb_index = milb.build_player_index(season, force=force)
        logger.info("MiLB Statcast 索引：%d 人（AAA/A 公开 tracking 范围）", len(milb_index))

        # 级别归因：现属球队 → 级别（精确），失败则逐行退回启发式
        level_map = self._resolve_current_levels(board, season)
        logger.info("级别归因：%d/%d 人解析到现属级别", len(level_map), len(board))

        rows: List[Dict[str, Any]] = []
        # Tier A 懒加载：仅当板上有已登板球员才拉 MLB 百分位快照
        pct_index: Dict[str, Dict[str, Any]] = {}
        if any("MLB" in str(p.get("levels", "")).upper() for p in board):
            pct_index = self._load_pct_index(season)

        for prospect in board:
            resolved = level_map.get(prospect.get("mlb_id"))
            proximity = compute_proximity(prospect, milb_index, resolved)
            if not include_far and proximity not in _DEFAULT_KEEP:
                continue
            is_hitter = str(prospect.get("position")) in _HITTER_POSITIONS
            tier, metrics, signals = self._assign_tier(
                prospect, is_hitter, proximity, milb_index, pct_index,
                milb, use_spring, season, force
            )
            rows.append({
                **{k: prospect.get(k) for k in
                   ("rank", "name", "team", "position", "age", "levels", "top_level", "mlb_id")},
                "is_hitter": is_hitter,
                # 展示用级别：归因结果优先，未归因退回 Pipeline 级别标记
                "level": resolved or prospect.get("top_level") or "—",
                "resolved_level": resolved,
                "proximity": proximity,
                "tier": tier,
                "metrics": metrics,
                "signals": signals,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df = self._attach_adp(df)
        df = self._score(df)
        return df.sort_values("composite", ascending=False).reset_index(drop=True)

    # -------------------------------------------------------------- 层级判定
    def _assign_tier(self, prospect: Dict[str, Any], is_hitter: bool,
                     proximity: str, milb_index: Dict[int, Dict[str, Any]],
                     pct_index: Dict[str, Dict[str, Any]],
                     milb: MilbStatcastFetcher,
                     use_spring: bool, season: int, force: bool):
        """按 A > B > D > C 取可用最高层，返回 (tier, metrics, signals)。

        metrics 为该层可得的 {指标名: 值}（统一百分数刻度）；signals 为人类可读说明。
        """
        name_key = _name_key(prospect.get("name"))
        pid = prospect.get("mlb_id")

        # Tier A：已登板，用 MLB 百分位快照
        if proximity == "已登板" and name_key in pct_index:
            row = pct_index[name_key]
            metrics, signals = self._tier_a_metrics(row, is_hitter)
            return "A", metrics, signals

        # Tier B：MiLB Statcast（AAA/A 公开 tracking）
        hit = milb_index.get(pid)
        if hit:
            metrics, signals = self._tier_b_metrics(hit, is_hitter)
            if metrics:
                return "B", metrics, signals

        # Tier D：春训（显式启用时；小样本，仅作新鲜度补充）
        if use_spring and pid:
            spring = milb.fetch_spring_stats(pid, "batter" if is_hitter else "pitcher",
                                             season, force=force)
            if spring:
                metrics, signals = self._tier_d_metrics(spring, is_hitter)
                if metrics:
                    return "D", metrics, signals

        # Tier C：Pipeline 内嵌比率统计兜底（含 AA 盲区）
        metrics, signals = self._tier_c_metrics(prospect.get("season_stats") or {}, is_hitter)
        return "C", metrics, signals

    @staticmethod
    def _load_pct_index(season: int) -> Dict[str, Dict[str, Any]]:
        """Savant 百分位快照按姓名建索引（懒加载，失败静默为空）。"""
        try:
            from ..data_fetch.savant_leaderboard import SavantLeaderboard
            lb = SavantLeaderboard()
            index: Dict[str, Dict[str, Any]] = {}
            for ptype in ("batter", "pitcher"):
                rows = lb.fetch_percentiles(ptype, season)
                for r in rows or []:
                    index.setdefault(_name_key(r.get("name")), r)
            return index
        except Exception as e:
            logger.debug("MLB 百分位快照不可用，Tier A 跳过: %s", e)
            return {}

    def _resolve_current_levels(self, board: List[Dict[str, Any]],
                                season: int) -> Dict[Any, str]:
        """级别归因：批量现属球队 + 球队级别映射（精确，替代级别标记猜测）。

        现属球队为 MLB 组织时须用当季 MLB 出场数二次验证——40 人名单
        未升班的新秀 currentTeam 也报母队（实测），GP>0 才算真登板；
        未登板者返回 None（该行退回接近度启发式）。任一环节失败返回 {}。
        """
        if self._stats_client is None:
            return {}
        try:
            ids = [p.get("mlb_id") for p in board if p.get("mlb_id")]
            people = self._stats_client.fetch_people_current_teams(ids, season)
            if not people:
                return {}
            team_level = self._stats_client.fetch_milb_team_level_map(season)
            if not team_level:
                return {}
            resolved: Dict[Any, str] = {}
            for pid, info in people.items():
                if not info or info.get("team_id") is None:
                    continue
                label = team_level.get(info["team_id"])
                if label is None:
                    continue
                if label == "MLB" and not info.get("mlb_gp"):
                    continue  # 40 人名单未登板：宁缺毋滥，退启发式
                resolved[pid] = label
            return resolved
        except Exception as e:
            logger.debug("级别归因失败，退回启发式: %s", e)
            return {}

    # ------------------------------------------------------ 各层指标提取
    @staticmethod
    def _tier_a_metrics(row: Dict[str, Any], is_hitter: bool):
        # 官方百分位本身就是 0-100，直接作为指标值
        if is_hitter:
            metrics = {"ev_pct": _num(row.get("exit_velocity")),
                       "xwoba_pct": _num(row.get("xwoba"))}
            return metrics, "MLB百分位：EV {_ev:.0f}/xwOBA {_xw:.0f}".format(
                _ev=metrics["ev_pct"] or 50, _xw=metrics["xwoba_pct"] or 50)
        metrics = {"velo_pct": _num(row.get("fb_velocity")),
                   "whiff_pct": _num(row.get("whiff_percent"))}
        return metrics, "MLB百分位：球速 {_v:.0f}/挥空 {_w:.0f}".format(
            _v=metrics["velo_pct"] or 50, _w=metrics["whiff_pct"] or 50)

    @staticmethod
    def _tier_b_metrics(hit: Dict[str, Any], is_hitter: bool):
        """批量聚合行的指标提取。

        列名按实测的批量 CSV 取（total_pitches/swing_miss_percent/launch_speed…），
        兼容逐人查询的列名（pitches）；挥空率优先直接取 swing_miss_percent。
        """
        stats = hit.get("stats") or {}
        pitches = _num(stats.get("total_pitches")) or _num(stats.get("pitches")) or 0
        if pitches <= 0:
            return {}, ""
        whiff_rate = _num(stats.get("swing_miss_percent"))
        if whiff_rate is None:
            whiffs = _num(stats.get("whiffs"))
            swings = _num(stats.get("swings")) or pitches
            whiff_rate = whiffs / swings * 100 if whiffs is not None and swings else None
        if is_hitter:
            # 打者挥空率越低越好（方向与投手相反，故拆成独立列）
            metrics = {"avg_ev": _num(stats.get("launch_speed")),
                       "xwoba_con": _num(stats.get("xwoba")),
                       "whiff_rate": whiff_rate}
            return metrics, "MiLB Statcast：EV {_ev:.1f}/xwOBA {_xw:.3f}".format(
                _ev=metrics["avg_ev"] or 0, _xw=metrics["xwoba_con"] or 0)
        metrics = {"fb_velo": _num(stats.get("velocity")),
                   "xwoba_against": _num(stats.get("xwoba")),
                   "p_whiff_rate": whiff_rate}
        return metrics, "MiLB Statcast：球速 {_v:.1f}/对手xwOBA {_xw:.3f}".format(
            _v=metrics["fb_velo"] or 0, _xw=metrics["xwoba_against"] or 0)

    @staticmethod
    def _tier_d_metrics(row: Dict[str, Any], is_hitter: bool):
        pitches = _num(row.get("pitches")) or 0
        if pitches <= 0:
            return {}, ""
        if is_hitter:
            metrics = {"avg_ev": _num(row.get("launch_speed")),
                       "xwoba_con": _num(row.get("xwoba"))}
            return metrics, "春训：EV {_ev:.1f}/xwOBA {_xw:.3f}（{n} 球，小样本）".format(
                _ev=metrics["avg_ev"] or 0, _xw=metrics["xwoba_con"] or 0, n=int(pitches))
        metrics = {"fb_velo": _num(row.get("velocity")),
                   "xwoba_against": _num(row.get("xwoba"))}
        return metrics, "春训：球速 {_v:.1f}/对手xwOBA {_xw:.3f}（{n} 球，小样本）".format(
            _v=metrics["fb_velo"] or 0, _xw=metrics["xwoba_against"] or 0, n=int(pitches))

    @staticmethod
    def _tier_c_metrics(stats: Dict[str, Any], is_hitter: bool):
        """比率类指标（K%/BB% 跨级别迁移性最好；计数类刻意不用，防低阶注水）。

        统一输出百分数刻度（0-100）。打者的 kPercent/bbPercent 由 MLB
        预计算（已是百分数）；投手的 strikePercentage 实为好球率不可用，
        改用 strikeOuts/battersFaced、baseOnBalls/battersFaced 自算。
        """
        if is_hitter:
            metrics = {"k_percent": _num(stats.get("kPercent")),
                       "bb_percent": _num(stats.get("bbPercent"))}
            if metrics["k_percent"] is None and metrics["bb_percent"] is None:
                return {}, ""
        else:
            bf = _num(stats.get("battersFaced")) or 0
            so, bb = _num(stats.get("strikeOuts")), _num(stats.get("baseOnBalls"))
            metrics = {"k_percent": so / bf * 100 if so is not None and bf else None,
                       "bb_percent": bb / bf * 100 if bb is not None and bf else None}
            if metrics["k_percent"] is None and metrics["bb_percent"] is None:
                return {}, ""
        signals = "Pipeline 比率：K% {_k}/BB% {_b}".format(
            _k="—" if metrics["k_percent"] is None else f"{metrics['k_percent']:.1f}",
            _b="—" if metrics["bb_percent"] is None else f"{metrics['bb_percent']:.1f}")
        return metrics, signals

    # -------------------------------------------------------------- ADP 与打分
    def _attach_adp(self, df: pd.DataFrame) -> pd.DataFrame:
        """按规范姓名合并 ADP，计算价值差（adp_rank − pipeline_rank，正 = 市场低估）。

        主 ADP（overall 榜 ~600 人）优先；deep ADP（+位置页并集 ~1000 人）
        只回填主榜缺失的姓名（新秀多在榜尾），合并后再统一算顺位与差值。
        """
        adp_df = self._adp_df
        if adp_df is None:
            try:
                from .adp import get_adp
                adp_df = get_adp()
            except Exception as e:
                logger.debug("ADP 不可用，价值差置中性: %s", e)
                adp_df = pd.DataFrame()

        def _to_map(frame: pd.DataFrame) -> Dict[str, float]:
            m = frame[["name", "adp"]].copy()
            m["name_key"] = m["name"].map(_name_key)
            m = m.dropna(subset=["adp"])
            return m.groupby("name_key", as_index=False)["adp"].min().set_index("name_key")["adp"].to_dict()

        main_map = _to_map(adp_df) if adp_df is not None and not adp_df.empty and "adp" in adp_df.columns else {}
        if self._deep_adp_enabled:
            try:
                from .adp import get_deep_adp
                deep_df = get_deep_adp()
                if deep_df is not None and not deep_df.empty:
                    deep_map = _to_map(deep_df)
                    # 仅回填主榜缺失（新秀多在 overall 榜尾之外）
                    for k, v in deep_map.items():
                        main_map.setdefault(k, v)
                    logger.info("deep ADP 补充后覆盖：%d 人", len(main_map))
            except Exception as e:
                logger.debug("deep ADP 不可用，仅用主 ADP: %s", e)

        df["name_key"] = df["name"].map(_name_key)
        df["pipeline_rank"] = df["rank"]
        df["adp"] = df["name_key"].map(main_map)
        df["adp_rank"] = df["adp"].rank(method="min", ascending=True)
        df["value_gap"] = df["adp_rank"] - df["pipeline_rank"]
        return df.drop(columns=["name_key"])

    @staticmethod
    def _pct_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
        """池内百分位（0-1）。NaN 不参与排名，结果保持 NaN。"""
        return series.rank(pct=True, ascending=ascending)

    def _score(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算各因子与综合分。因子列独立输出，保持可解释性。"""
        board_size = max(len(df), 1)
        df["talent_prior"] = (board_size + 1 - df["pipeline_rank"]) / board_size
        df["proximity_score"] = df["proximity"].map(_PROXIMITY_SCORE).astype(float)

        # 展开指标字典为列
        for col in _METRIC_DIRECTIONS:
            df[col] = df["metrics"].map(
                lambda m, c=col: (m or {}).get(c) if isinstance(m, dict) else None
            )

        # 指标分：优先"同层+同类型+同级别带"池（消除低级别 K% 注水偏置），
        # 池太小（<3 人）退回"同层+同类型"全池，仍不足（<2 人）则该指标跳过
        def metric_score_row(row) -> float:
            sub = []
            tier_pool = df[(df["tier"] == row["tier"]) & (df["is_hitter"] == row["is_hitter"])]
            band = _LEVEL_BANDS.get(row.get("level"))
            band_pool = tier_pool[
                tier_pool["level"].map(lambda l: _LEVEL_BANDS.get(l)) == band
            ] if band else tier_pool
            for col, invert in _METRIC_DIRECTIONS.items():
                val = row.get(col)
                if val is None or pd.isna(val):
                    continue
                pool = None
                if band is not None and band_pool[col].notna().sum() >= 3:
                    pool = band_pool
                elif tier_pool[col].notna().sum() >= 2:
                    pool = tier_pool
                if pool is None:
                    continue
                pct = self._pct_rank(pool[col], ascending=invert)
                sub.append(float(pct[row.name]))
            return sum(sub) / len(sub) if sub else 0.5

        df["metric_score"] = df.apply(metric_score_row, axis=1)

        gap = df["value_gap"].astype(float).clip(_GAP_CLIP_LOW, _GAP_CLIP_HIGH)
        df["value_score"] = ((gap - _GAP_CLIP_LOW) /
                             (_GAP_CLIP_HIGH - _GAP_CLIP_LOW)).fillna(0.5)
        df["composite"] = (_W_TALENT * df["talent_prior"]
                           + _W_METRIC * df["metric_score"]
                           + _W_PROXIMITY * df["proximity_score"]
                           + _W_VALUE * df["value_score"]).round(4)
        return df

    # -------------------------------------------------------------- 入库
    @staticmethod
    def save_snapshot(df: pd.DataFrame, season: Optional[int] = None) -> int:
        """把雷达结果追加为 DB 快照（rank 历史序列，post-hype 检测打底）。"""
        if df is None or df.empty:
            return 0
        from ..db import ProspectRepository, db_session
        season = season or get_season()
        with db_session() as conn:
            return ProspectRepository(conn).save_snapshot(df.to_dict("records"), season)


# 各指标的排序方向：True = 值越大越好；False = 越小越好
# 打者与投手方向不同（如 K%），故列名拆分（k_percent / p 层自算同列但分池打分）
_METRIC_DIRECTIONS = {
    "ev_pct": True, "xwoba_pct": True,          # Tier A 打者（已是百分位）
    "velo_pct": True, "whiff_pct": True,        # Tier A 投手
    "avg_ev": True, "xwoba_con": True,          # Tier B/D 打者
    "fb_velo": True, "xwoba_against": False,    # Tier B/D 投手
    "whiff_rate": False,                         # Tier B 打者挥空率（越低越好）
    "p_whiff_rate": True,                        # Tier B 投手挥空率（越高越好）
    "k_percent": False, "bb_percent": True,     # Tier C 比率（K% 越低越好）
}

# 级别 → 池分组（低级别打者面对弱投手 K% 天然好看，跨带比较会系统性
# 偏向低级别球员；C 层百分位优先在同带内比）
_LEVEL_BANDS = {"MLB": "upper", "AAA": "upper", "AA": "upper",
                "A+": "mid", "A": "lower", "RC": "lower", "ROK": "lower"}
