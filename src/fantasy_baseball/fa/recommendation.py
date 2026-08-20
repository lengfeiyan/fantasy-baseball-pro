"""FA 推荐系统。

迁移自旧版 ``fa_analyzer/recommendation.py``。根据阵容需求、风险偏好生成
FA 球员推荐。算法与旧版一致，DB 访问走仓储层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import get_config, history_path, output_path
from ..db import RosterRepository, db_session
from ..utils.logger import get_logger
from .analyzer import FAAnalyzer

logger = get_logger("fa.recommendation")

# 池/阵容的原始 pos → 槽位键（与 analyzer 的位置归一化同口径；
# P 为泛投手，按 SP 计缺口）
_SLOT_NORMALIZE = {
    "LF": "OF", "CF": "OF", "RF": "OF", "DH": "UTIL", "P": "SP",
}


def _normalize_slot(pos) -> str:
    """把 FA 池/阵容的原始位置归一化到 roster_slots 键。"""
    if not pos:
        return ""
    return _SLOT_NORMALIZE.get(str(pos), str(pos))


class RecommendationSystem:
    """FA 推荐系统。"""

    def __init__(self, fa_analyzer: Optional[FAAnalyzer] = None, conn=None):
        self._conn = conn
        self.fa_analyzer = fa_analyzer or FAAnalyzer(conn=conn)
        cfg = get_config()
        self.roster_slots = cfg["league"]["roster_slots"]
        # 修复审计项：偏好作为全局乘数不改变排序（保守=激进同序）。
        # 改为伤病惩罚的放大/衰减系数：conservative 放大惩罚、aggressive 衰减。
        self.risk_preferences = {"conservative": 1.5, "balanced": 1.0, "aggressive": 0.5}

    # -------------------------------------------------------------- 阵容需求
    def analyze_roster_needs(self, user_roster: Optional[List[Dict]] = None) -> Dict[str, float]:
        """分析阵容各位置需求强度（0-1）。

        修复审计项：roster 里的原始 pos（CF/LF/RF/DH/P 等）先归一化到
        槽位键（OF/UTIL/SP…），否则这些球员不被计数、缺口被高估。
        """
        if not user_roster:
            user_roster = self._load_user_roster()

        counts = {pos: 0 for pos in self.roster_slots}
        for p in user_roster:
            pos = _normalize_slot(p.get("pos"))
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
        cancel_check=None,
    ) -> List[Dict[str, Any]]:
        """生成 FA 推荐。cancel_check 为可选取消回调（评估每个球员前检查）。"""
        logger.info("生成推荐：位置=%s, top=%d, 风险=%s", position, top_n, risk_preference)
        needs = self.analyze_roster_needs(user_roster)
        fa_pool = self.fa_analyzer.get_fa_pool(position)
        if not fa_pool:
            logger.warning("FA 池为空")
            return []

        evaluations = []
        for player in fa_pool:
            # 支持中途取消
            if cancel_check is not None and cancel_check():
                logger.info("FA 推荐被取消")
                return []
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
        # 修复 H4：player_id 为空（None 或 NaN）时，用姓名搜索 MLB id 兜底。
        # 否则文档说"player_id 可留空"但推荐系统静默丢弃这些球员。
        import pandas as pd
        if pid is None or (isinstance(pid, float) and pd.isna(pid)):
            name = player.get("name")
            if not name:
                return None
            try:
                from ..data_fetch.mlb_api import MLBStatsClient
                person = MLBStatsClient().search_player(name)
                if not person:
                    logger.info("无法从姓名解析 MLB id，跳过: %s", name)
                    return None
                pid = person["id"]
            except Exception as e:
                logger.warning("按姓名搜索 MLB id 失败 (%s): %s", name, e)
                return None

        value = self.fa_analyzer.calculate_fa_value(int(pid))
        pos = player.get("pos")
        # 修复审计项：池内 pos（CF/LF/RF/DH/P 等）归一化后再查需求表，
        # 否则一律落到默认 0.5，真实缺口位置拿不到加成
        need_factor = needs.get(_normalize_slot(pos), 0.5)
        risk_adj = self._calculate_risk_adjustment(int(pid), risk_preference)
        final_score = value["overall_value"] * (1 + need_factor * 0.5) * risk_adj
        return {
            "player_id": int(pid),
            "name": player.get("name"),
            "team": player.get("team"),
            "pos": pos,
            "value": value,
            "need_factor": need_factor,
            "risk_adjustment": risk_adj,
            "final_score": final_score,
            "is_mock": bool(value.get("is_mock", False)),
        }

    def _calculate_risk_adjustment(self, player_id: int, risk_preference: str) -> float:
        """风险调整因子（含伤病与偏好）。

        修复审计项：偏好作为全局乘数不改变排序（保守=激进同序）。
        改为幂缩放：conservative（指数 1.5）放大伤病惩罚、aggressive
        （指数 0.5）衰减，balanced 即原始因子。幂缩放天然落在 (0, 1]，
        不会被上限抵消（线性放大 (1-因子)×1.5 会被 min(1.0) 截断成无惩罚）。
        """
        risk_factor = 1.0
        try:
            details = self.fa_analyzer.get_player_details(player_id)
            injury = details.get("injury")
            if injury:
                severity = injury.get("severity", "mild")
                factors = {"mild": 0.95, "moderate": 0.8, "severe": 0.6, "long_term": 0.3}
                injury_factor = factors.get(severity, 0.95)
                pref_exp = self.risk_preferences.get(risk_preference, 1.0)
                risk_factor = injury_factor ** pref_exp
        except Exception as e:
            logger.warning("获取球员 %d 详情失败: %s", player_id, e)
        return min(risk_factor, 1.0)

    # -------------------------------------------------------------- 导出
    def export_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        output_file: str,
        method: str = "vorp",
        risk_preference: str = "balanced",
    ) -> str:
        """导出推荐并持久化（DB 会话 + 时间戳备份 + 最近一份同名 CSV）。"""
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
                "need_factor": r.get("need_factor"),
                "risk_adjustment": r.get("risk_adjustment"),
                "is_mock": bool(r.get("is_mock", False)),
            }
            rows.append(row)
        df = pd.DataFrame(rows)

        # 1. DB（会话式追加）
        import datetime as _dt

        session_id = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            from ..db import RecommendationRepository, db_session

            with db_session() as conn:
                RecommendationRepository(conn).save_session(
                    session_id, rows, method=method, risk_preference=risk_preference
                )
            logger.info("FA 推荐已写入数据库（会话 %s，%d 条）", session_id, len(rows))
        except Exception as e:
            logger.warning("FA 推荐写入数据库失败: %s", e)

        # 2. CSV：最近一份 + 时间戳备份
        path = output_path(output_file)
        df.to_csv(path, index=False)
        try:
            backup = history_path(output_file)
            df.to_csv(backup, index=False)
        except OSError as e:
            logger.warning("写入 FA 推荐历史备份失败: %s", e)

        logger.info("推荐已导出: %s", path)
        return path

    # -------------------------------------------------------------- 工具
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
