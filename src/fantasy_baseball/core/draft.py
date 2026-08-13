"""蛇形选秀模拟器（单次）。

迁移自旧版 ``snake_draft_simulator_pro.py``，改用 ScoringModel 直接生成排名
（不再读 CSV 或裸 SQL）。三种策略（conservative / balanced / aggressive），
自动处理位置需求与稀缺性加成。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from ..config import get_config, resolve_path
from ..utils.logger import get_logger
from .adp import ADPCache
from .scoring import ScoringModel

logger = get_logger("draft")

VALUE_PICK_THRESHOLD = 5  # ADP 低于预期顺位超过此值视为价值股


class SnakeDraftSimulator:
    """单次蛇形选秀模拟器。"""

    def __init__(self, rankings: Optional[pd.DataFrame] = None, method: str = "vorp"):
        """Args:
            rankings: 预计算的排名 DataFrame。None 则现算（按 method）。
            method: 评分方法 "vorp" 或 "sgp"。决定排序列和默认排名计算。
        """
        cfg = get_config()
        self.league_size = cfg["league"]["size"]
        self.rounds = cfg["league"]["rounds"]
        self.roster_slots = cfg["league"]["roster_slots"]
        self.default_strategy = cfg["draft_simulator"]["default_strategy"]
        self.show_value_picks = cfg["draft_simulator"]["show_value_picks"]
        self.method = method

        if rankings is not None:
            self.rankings = rankings
        elif method == "sgp":
            from .sgp import SGPModel
            self.rankings = SGPModel().calculate_sgp()
        else:
            self.rankings = ScoringModel().calculate_vorp()
        try:
            self.adp = ADPCache().fetch_adp()
        except Exception:
            self.adp = pd.DataFrame(columns=["name", "pos", "adp"])

        self.drafted_players: set = set()
        self.team_rosters: Dict[int, Dict] = {}

    @property
    def _value_col(self) -> str:
        """当前评分方法对应的价值列名。"""
        return "sgp_total" if self.method == "sgp" else "vorp"

    def simulate_draft(self, user_pick: int = 1, strategy: Optional[str] = None) -> pd.DataFrame:
        """模拟一次完整选秀，返回选秀日志 DataFrame。"""
        if not 1 <= user_pick <= self.league_size:
            raise ValueError(f"选秀顺位必须在 1-{self.league_size} 之间")
        strategy = strategy or self.default_strategy
        logger.info("开始模拟选秀：第 %d 顺位，策略 %s", user_pick, strategy)

        self.drafted_players = set()
        self.team_rosters = {t: {"picks": [], "roster": {}} for t in range(1, self.league_size + 1)}

        draft_log: List[Dict] = []
        for round_num in range(1, self.rounds + 1):
            # 蛇形：奇数轮顺序，偶数轮逆序
            order = (
                list(range(1, self.league_size + 1))
                if round_num % 2 == 1
                else list(range(self.league_size, 0, -1))
            )
            for pick_num, team_id in enumerate(order, 1):
                total_pick = (round_num - 1) * self.league_size + pick_num
                player = self._select_player(team_id, strategy)
                if player is None:
                    continue
                self.drafted_players.add(player["name"])
                self.team_rosters[team_id]["picks"].append(player)
                self.team_rosters[team_id]["roster"][len(self.team_rosters[team_id]["roster"])] = player

                expected = self._expected_pick(player["name"])
                draft_log.append({
                    "round": round_num,
                    "pick": total_pick,
                    "team": team_id,
                    "name": player["name"],
                    "team_name": player.get("team"),
                    "pos": player.get("pos"),
                    "vorp": player.get("vorp", 0),
                    "vorp_upside": player.get("vorp_upside", 0),
                    "vorp_floor": player.get("vorp_floor", 0),
                    "sgp_total": player.get("sgp_total", 0),
                    "adp": self._player_adp(player["name"]),
                    "is_user_pick": team_id == user_pick,
                    "is_value_pick": self._is_value_pick(total_pick, player["name"]),
                })

        log_df = pd.DataFrame(draft_log)
        logger.info("选秀模拟完成，共 %d 次选择", len(log_df))
        return log_df

    def simulate_and_save(
        self, user_pick: int = 1, strategy: Optional[str] = None, output_file: Optional[str] = None
    ) -> str:
        """模拟并保存日志到 CSV，返回绝对路径。"""
        log_df = self.simulate_draft(user_pick, strategy)
        if output_file is None:
            output_file = f"draft_log_pick{user_pick}_{strategy or self.default_strategy}.csv"
        path = resolve_path(output_file)
        log_df.to_csv(path, index=False)
        logger.info("选秀日志已保存: %s", path)
        return path

    # -------------------------------------------------------------- 内部
    def _select_player(self, team_id: int, strategy: str) -> Optional[Dict]:
        """为球队选择最佳球员，考虑位置需求与稀缺性。"""
        available = self.rankings[~self.rankings["name"].isin(self.drafted_players)]
        if available.empty:
            return None

        # 按策略排序
        if self.method == "sgp":
            # SGP 没有 upside/floor，所有策略都用 sgp_total
            sort_col = "sgp_total" if "sgp_total" in available.columns else "vorp"
        else:
            sort_col = {"aggressive": "vorp_upside", "conservative": "vorp_floor"}.get(strategy, "vorp")
            sort_col = sort_col if sort_col in available.columns else "vorp"
        available = available.sort_values(sort_col, ascending=False)

        pos_counts = self._team_pos_counts(team_id)
        best, best_score = None, -float("inf")
        for _, player in available.iterrows():
            pos = player.get("pos")
            # 位置已满则跳过（UTIL 例外）
            if pos_counts.get(pos, 0) >= self.roster_slots.get(pos, 0) and pos != "UTIL":
                continue
            score = float(player.get(sort_col, 0))
            # 稀缺位置 10% 加成
            if pos_counts.get(pos, 0) < self.roster_slots.get(pos, 0):
                score *= 1.1
            if score > best_score:
                best_score, best = score, player.to_dict()

        return best if best is not None else (available.iloc[0].to_dict() if not available.empty else None)

    def _team_pos_counts(self, team_id: int) -> Dict[str, int]:
        counts = {pos: 0 for pos in self.roster_slots}
        for p in self.team_rosters[team_id]["roster"].values():
            pos = p.get("pos")
            if pos in counts:
                counts[pos] += 1
        return counts

    def _player_adp(self, name: str) -> Optional[float]:
        hit = self.adp[self.adp["name"] == name]
        return float(hit.iloc[0]["adp"]) if not hit.empty else None

    def _expected_pick(self, name: str) -> Optional[int]:
        hit = self.adp[self.adp["name"] == name]
        return int(hit.iloc[0]["adp"]) if not hit.empty else None

    def _is_value_pick(self, total_pick: int, name: str) -> bool:
        """判断是否为价值股（实际顺位远低于 ADP）。"""
        if not self.show_value_picks:
            return False
        adp = self._player_adp(name)
        return adp is not None and (adp - total_pick) > VALUE_PICK_THRESHOLD
