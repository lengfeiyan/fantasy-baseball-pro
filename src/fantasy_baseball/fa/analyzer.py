"""FA 球员价值分析引擎。

迁移自旧版 ``fa_analyzer/fa_analyzer.py``。综合价值评分、伤病调整、位置稀缺性、
Statcast 评分算法与旧版完全一致。所有 DB 访问走仓储层。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..db import FaRepository, InjuryRepository, db_session
from ..utils.logger import get_logger
from .real_time import RealTimeData

logger = get_logger("fa.analyzer")

# 含具体外野位置（MLB API 返回 CF/RF/LF 而非 OF），内部统一归一化为 OF
HITTER_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "LF", "CF", "RF", "DH"}
PITCHER_POSITIONS = {"SP", "RP", "P"}

# 位置归一化映射（具体外野 → OF）
_POSITION_NORMALIZE = {"LF": "OF", "CF": "OF", "RF": "OF", "DH": "UTIL"}


def _normalize_pos(pos: str) -> str:
    """把 MLB 具体位置归一化为项目标准位置。"""
    if not pos:
        return ""
    return _POSITION_NORMALIZE.get(pos, pos)


def _current_season() -> int:
    """当前赛季年份。"""
    return datetime.now().year


def _safe_f(v) -> Optional[float]:
    """安全转 float。"""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class FAAnalyzer:
    """FA 球员分析引擎。

    Args:
        conn: 可选数据库连接。
        method: 评分方法 "vorp"（线性加权，默认）或 "sgp"（SGP 分母）。
    """

    def __init__(self, conn=None, method: str = "vorp"):
        self._conn = conn
        self.method = method
        cfg = get_config()
        self.scoring_rules = cfg["league"]["scoring"]
        # SGP 分母（method=sgp 时用）
        sgp_cfg = cfg.get("sgp", {})
        self.sgp_hitter_denoms = sgp_cfg.get("denominators", {}).get("hitters", {})
        self.sgp_pitcher_denoms = sgp_cfg.get("denominators", {}).get("pitchers", {})
        self.position_scarcity = {
            "C": 1.3, "SS": 1.2, "2B": 1.1, "3B": 1.05,
            "1B": 0.9, "OF": 0.85, "SP": 1.0, "RP": 1.15,
        }
        self.injury_factors = {
            "mild": 0.85, "moderate": 0.65, "severe": 0.4, "long_term": 0.15,
        }

    # -------------------------------------------------------------- FA 池
    def get_fa_pool(self, position: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取 FA 池列表。"""
        def _do(conn):
            df = FaRepository(conn).get_pool(position)
            return df.to_dict("records")
        return self._run(_do)

    # -------------------------------------------------------------- 价值计算
    def calculate_fa_value(self, player_id: int) -> Dict[str, Any]:
        """计算 FA 球员综合价值。"""
        rtd = RealTimeData(conn=self._conn)
        stats = rtd.fetch_player_stats(player_id)
        # 归一化位置（MLB API 返回 CF/RF/LF → OF），统一供下游评分使用
        stats["pos"] = _normalize_pos(stats.get("pos", ""))

        base_score = self._calculate_base_score(stats)
        trend_score = self._calculate_trend_score(player_id, stats)
        injury_adjusted = self._adjust_for_injury(player_id, base_score)
        position_adjusted = self._adjust_for_position_scarcity(stats.get("pos"), injury_adjusted)
        statcast_score = self._calculate_statcast_score(stats)
        overall = self._calculate_overall_value(position_adjusted, trend_score, statcast_score)

        return {
            "player_id": player_id,
            "name": stats.get("name"),
            "pos": stats.get("pos"),
            "base_score": base_score,
            "trend_score": trend_score,
            "injury_adjusted_value": injury_adjusted,
            "position_adjusted_value": position_adjusted,
            "statcast_score": statcast_score,
            "overall_value": overall,
        }

    def _calculate_base_score(self, player_stats: Dict[str, Any]) -> float:
        pos = player_stats.get("pos", "")
        stats = player_stats.get("stats", {})
        score = 0.0

        if self.method == "sgp":
            # SGP 模式：用 SGP 分母算各类别贡献
            if pos in HITTER_POSITIONS:
                denoms = self.sgp_hitter_denoms
            elif pos in PITCHER_POSITIONS:
                denoms = self.sgp_pitcher_denoms
            else:
                denoms = {}
            for stat, denom in denoms.items():
                if stat in stats and denom and denom != 0:
                    val = _safe_f(stats[stat])
                    if val is not None:
                        score += val / denom
            return score

        # VORP 模式：线性加权
        if pos in HITTER_POSITIONS:
            weights = self.scoring_rules.get("hitters", {})
        elif pos in PITCHER_POSITIONS:
            weights = self.scoring_rules.get("pitchers", {})
        else:
            weights = {}
        for stat, weight in weights.items():
            if stat in stats:
                score += stats[stat] * weight
        return score

    def _calculate_trend_score(self, player_id: int, player_stats: Dict[str, Any]) -> float:
        """趋势分：近期表现 vs 赛季均值。

        基准 100（与赛季持平）。近期表现好于赛季 → >100（上升）；
        差于赛季 → <100（下降）。获取失败时返回 100（中性，不惩罚也不奖励）。

        对打者：用近期 OPS 近似 vs 赛季 OPS。
        对投手：用近期 ERA 反向（低 ERA = 好 → 高趋势分）。
        """
        from ..data_fetch.mlb_api import MLBStatsClient

        season_stats = player_stats.get("stats", {})
        pos = player_stats.get("pos", "")

        try:
            client = MLBStatsClient()
            recent = client.fetch_recent_performance(player_id, _current_season(), last_n_games=10)
            if not recent:
                return 100.0

            if pos in HITTER_POSITIONS:
                # 打者：近期 OPS 近似 vs 赛季 OPS
                season_ops = _safe_f(season_stats.get("OPS"))
                recent_ops = recent.get("ops_approx")
                if season_ops and recent_ops and season_ops > 0:
                    ratio = recent_ops / season_ops
                    return round(100.0 * ratio, 1)
            elif pos in PITCHER_POSITIONS:
                # 投手：近期 ERA 反向对比（低 ERA 好）
                season_era = _safe_f(season_stats.get("ERA"))
                recent_era = recent.get("era_recent")
                if season_era and recent_era and recent_era > 0:
                    ratio = season_era / recent_era  # 赛季/近期，近期低则>1
                    return round(100.0 * ratio, 1)
        except Exception as e:
            logger.debug("趋势分计算失败 (id=%d): %s", player_id, e)

        return 100.0  # 中性兜底

    def _adjust_for_injury(self, player_id: int, base_score: float) -> float:
        def _do(conn):
            row = conn.execute(
                "SELECT severity FROM injury_reports "
                "WHERE player_id=? AND status!='recovered' "
                "ORDER BY start_date DESC LIMIT 1",
                (player_id,),
            ).fetchone()
            return row["severity"] if row else None
        severity = self._run(_do)
        if severity:
            factor = self.injury_factors.get(severity, 1.0)
            return base_score * factor
        return base_score

    def _adjust_for_position_scarcity(self, position: Optional[str], value: float) -> float:
        factor = self.position_scarcity.get(position or "", 1.0)
        return value * factor

    def _calculate_statcast_score(self, player_stats: Dict[str, Any]) -> float:
        sc = player_stats.get("statcast", {})
        if not sc:
            return 0.0
        pos = player_stats.get("pos", "")
        if pos in HITTER_POSITIONS:
            score = (
                sc.get("xwOBA", 0) * 300
                + sc.get("barrel_rate", 0) * 100
                + sc.get("exit_velocity", 0)
                + sc.get("hard_hit_rate", 0) * 100
                + sc.get("swing_contact_rate", 0) * 100
            )
        elif pos in PITCHER_POSITIONS:
            score = (
                (3 - sc.get("xERA", 5)) * 20
                + sc.get("whiff_rate", 0) * 100
                + sc.get("spin_rate", 0) * 0.1
                + sc.get("velocity", 0) * 2
                + (1 - sc.get("hard_hit_allowed_rate", 1)) * 100
            )
        else:
            score = 0.0
        return float(max(0, min(score, 100)))

    def _calculate_overall_value(
        self, position_adjusted: float, trend_score: float, statcast_score: float
    ) -> float:
        """综合价值（权重与旧版一致）。"""
        weights = {"position_adjusted": 0.3, "trend": 0.15, "statcast": 0.25, "vorp": 0.3}
        return (
            position_adjusted * weights["position_adjusted"]
            + trend_score * weights["trend"]
            + statcast_score * weights["statcast"]
            + position_adjusted * weights["vorp"]
        )

    # -------------------------------------------------------------- 球员详情
    def get_player_details(self, player_id: int) -> Dict[str, Any]:
        """获取球员详情（统计 + 价值 + 伤病）。"""
        value = self.calculate_fa_value(player_id)

        def _do(conn):
            row = conn.execute(
                "SELECT * FROM injury_reports WHERE player_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (player_id,),
            ).fetchone()
            return dict(row) if row else None
        injury = self._run(_do)
        value["injury"] = injury
        return value

    # -------------------------------------------------------------- 工具
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
