"""FA 推荐系统。

迁移自旧版 ``fa_analyzer/recommendation.py``。根据阵容需求、风险偏好生成
FA 球员推荐。算法与旧版一致，DB 访问走仓储层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import get_config
from ..db import RosterRepository, db_session
from ..utils.logger import get_logger
from .analyzer import FAAnalyzer

logger = get_logger("fa.recommendation")


class RecommendationSystem:
    """FA 推荐系统。"""

    def __init__(self, fa_analyzer: Optional[FAAnalyzer] = None, conn=None):
        self._conn = conn
        self.fa_analyzer = fa_analyzer or FAAnalyzer(conn=conn)
        cfg = get_config()
        self.roster_slots = cfg["league"]["roster_slots"]
        self.risk_preferences = {"conservative": 0.8, "balanced": 1.0, "aggressive": 1.2}

    # -------------------------------------------------------------- 阵容需求
    def analyze_roster_needs(self, user_roster: Optional[List[Dict]] = None) -> Dict[str, float]:
        """分析阵容各位置需求强度（0-1）。"""
        if not user_roster:
            user_roster = self._load_user_roster()

        counts = {pos: 0 for pos in self.roster_slots}
        for p in user_roster:
            pos = p.get("pos")
            if pos in counts:
                counts[pos] += 1

        needs: Dict[str, float] = {}
        for pos, required in self.roster_slots.items():
            current = counts.get(pos, 0)
            base_need = max(0.0, (required - current) / required) if required > 0 else 0.0
            needs[pos] = min(1.0, base_need)
        return needs

    def _load_user_roster(self) -> List[Dict]:
        """从数据库读取用户阵容。"""
        def _do(conn):
            df = RosterRepository(conn).get_roster()
            return df.to_dict("records")
        try:
            return self._run(_do)
        except Exception:
            return []

    # -------------------------------------------------------------- 推荐生成
    def generate_recommendations(
        self,
        user_roster: Optional[List[Dict]] = None,
        position: Optional[str] = None,
        top_n: int = 10,
        risk_preference: str = "balanced",
    ) -> List[Dict[str, Any]]:
        """生成 FA 推荐。"""
        logger.info("生成推荐：位置=%s, top=%d, 风险=%s", position, top_n, risk_preference)
        needs = self.analyze_roster_needs(user_roster)
        fa_pool = self.fa_analyzer.get_fa_pool(position)
        if not fa_pool:
            logger.warning("FA 池为空")
            return []

        evaluations = []
        for player in fa_pool:
            try:
                ev = self._evaluate_player(player, needs, risk_preference)
                if ev:
                    evaluations.append(ev)
            except Exception as e:
                logger.warning("评估球员 %s 失败: %s", player.get("name"), e)

        evaluations.sort(key=lambda x: x["final_score"], reverse=True)
        return evaluations[:top_n]

    def _evaluate_player(
        self, player: Dict[str, Any], needs: Dict[str, float], risk_preference: str
    ) -> Optional[Dict[str, Any]]:
        pid = player.get("player_id")
        if pid is None:
            return None
        value = self.fa_analyzer.calculate_fa_value(pid)
        pos = player.get("pos")
        need_factor = needs.get(pos, 0.5)
        risk_adj = self._calculate_risk_adjustment(pid, risk_preference)
        final_score = value["overall_value"] * (1 + need_factor * 0.5) * risk_adj
        return {
            "player_id": pid,
            "name": player.get("name"),
            "team": player.get("team"),
            "pos": pos,
            "value": value,
            "need_factor": need_factor,
            "risk_adjustment": risk_adj,
            "final_score": final_score,
        }

    def _calculate_risk_adjustment(self, player_id: int, risk_preference: str) -> float:
        """风险调整因子（含伤病与偏好）。"""
        risk_factor = 1.0
        try:
            details = self.fa_analyzer.get_player_details(player_id)
            injury = details.get("injury")
            if injury:
                severity = injury.get("severity", "mild")
                factors = {"mild": 0.95, "moderate": 0.8, "severe": 0.6, "long_term": 0.3}
                risk_factor *= factors.get(severity, 0.95)
        except Exception as e:
            logger.warning("获取球员 %d 详情失败: %s", player_id, e)
        pref = self.risk_preferences.get(risk_preference, 1.0)
        return risk_factor * pref

    # -------------------------------------------------------------- 导出
    def export_recommendations(
        self, recommendations: List[Dict[str, Any]], output_file: str
    ) -> str:
        """导出推荐到 CSV，返回绝对路径。"""
        from ..config import resolve_path

        rows = []
        for r in recommendations:
            row = {
                "player_id": r["player_id"],
                "name": r["name"],
                "team": r["team"],
                "pos": r["pos"],
                "final_score": r["final_score"],
                "overall_value": r["value"]["overall_value"],
                "base_score": r["value"]["base_score"],
                "statcast_score": r["value"]["statcast_score"],
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        path = resolve_path(output_file)
        df.to_csv(path, index=False)
        logger.info("推荐已导出: %s", path)
        return path

    # -------------------------------------------------------------- 工具
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
