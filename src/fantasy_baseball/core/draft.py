"""蛇形选秀模拟器（单次）。

迁移自旧版 ``snake_draft_simulator_pro.py``，改用 ScoringModel 直接生成排名
（不再读 CSV 或裸 SQL）。三种策略（conservative / balanced / aggressive），
自动处理位置需求与稀缺性加成。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from ..config import get_config, output_path
from ..utils.logger import get_logger
from .adp import ADPCache
from .scoring import ScoringModel

logger = get_logger("draft")

VALUE_PICK_THRESHOLD = 5  # ADP 低于预期顺位超过此值视为价值股

# 联盟典型团队赛季总量（12 队经验值），用于类别平衡的跨量纲归一化
_CAT_TYPICAL_TOTAL = {
    "R": 1000.0, "HR": 250.0, "RBI": 1000.0, "SB": 120.0,
    "W": 75.0, "SV": 60.0, "K": 1300.0, "ERA": 3.8, "WHIP": 1.25,
}


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
                player = self._select_player(team_id, strategy, user_pick)
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
                    # 修复 L4：SGP 排名没有 vorp 列，日志里 vorp 全 0，
                    # 导致阵容强度分析显示错误。SGP 时用 sgp_total 填充 vorp 列。
                    "vorp": player.get("vorp", player.get("sgp_total", 0)),
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
        self,
        user_pick: int = 1,
        strategy: Optional[str] = None,
        output_file: Optional[str] = None,
        log_df: Optional[pd.DataFrame] = None,
    ) -> str:
        """模拟并保存日志到 CSV，返回绝对路径。

        修复 L1：此前 GUI 先调 simulate_draft 展示、再调 simulate_and_save 保存，
        导致选秀被执行两遍（两次结果可能不一致）。现支持传入已算好的 log_df。
        """
        if log_df is None:
            log_df = self.simulate_draft(user_pick, strategy)
        if output_file is None:
            output_file = f"draft_log_pick{user_pick}_{strategy or self.default_strategy}.csv"
        path = output_path(output_file)
        log_df.to_csv(path, index=False)
        logger.info("选秀日志已保存: %s", path)
        return path

    # -------------------------------------------------------------- 内部
    def _select_player(self, team_id: int, strategy: str, user_pick: int = 0) -> Optional[Dict]:
        """为球队选择最佳球员，考虑位置需求、稀缺性与类别平衡。"""
        available = self.rankings[~self.rankings["name"].isin(self.drafted_players)]
        if available.empty:
            return None

        # 按策略排序
        if self.method == "sgp":
            sort_col = "sgp_total" if "sgp_total" in available.columns else "vorp"
        else:
            sort_col = {"aggressive": "vorp_upside", "conservative": "vorp_floor"}.get(strategy, "vorp")
            sort_col = sort_col if sort_col in available.columns else "vorp"
        available = available.sort_values(sort_col, ascending=False)

        pos_counts = self._team_pos_counts(team_id)
        # 类别平衡：仅对用户球队生效，跟踪已选球员的 5×5 类别
        is_user = (team_id == user_pick)
        cat_totals = self._team_category_totals(team_id) if is_user else None
        HITTER_STATS = ("HR", "SB", "R", "RBI")
        PITCHER_STATS = ("W", "SV", "K")

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
            # 类别平衡 bonus（仅用户球队）：如果该球员补的是弱势类别，加分
            if is_user and cat_totals:
                balance_bonus = self._category_balance_bonus(player, cat_totals, HITTER_STATS, PITCHER_STATS)
                score += balance_bonus
            if score > best_score:
                best_score, best = score, player.to_dict()

        return best if best is not None else (available.iloc[0].to_dict() if not available.empty else None)

    def _team_category_totals(self, team_id: int) -> Dict[str, float]:
        """统计用户已选球员的 5×5 类别累计。"""
        totals: Dict[str, float] = {}
        stats = ("HR", "SB", "R", "RBI", "AVG", "W", "SV", "K", "ERA", "WHIP")
        for s in stats:
            totals[s] = 0.0
        for p in self.team_rosters[team_id]["roster"].values():
            for s in stats:
                val = p.get(s)
                if val is not None:
                    try:
                        totals[s] += float(val)
                    except (ValueError, TypeError):
                        pass
        return totals

    def _category_balance_bonus(
        self, player: pd.Series, cat_totals: Dict[str, float],
        hitter_stats: tuple, pitcher_stats: tuple,
    ) -> float:
        """计算类别平衡 bonus。

        逻辑：找出阵容里最弱的类别（累计值最低），如果该球员在弱类上有高预测值，
        给一个 bonus。bonus 量级约为 sort_col 的 10-15%，避免压过主排序。
        """
        pos = player.get("pos", "")
        bonus = 0.0

        # 打者：看 HR/SB/R/RBI 是否偏科。
        # 修复审计项：R/RBI（~1000）与 SB（~80）原始值不可比，旧逻辑恒把
        # R/RBI 当最强、SB/HR 当最弱。先按联盟典型团队总量归一化再比较。
        if pos not in ("SP", "RP"):
            cat_values = []
            for s in hitter_stats:
                val = player.get(s)
                if val is not None:
                    try:
                        cat_values.append(
                            (s, float(val) / _CAT_TYPICAL_TOTAL.get(s, 1.0))
                        )
                    except (ValueError, TypeError):
                        pass
            if cat_values and len(cat_values) >= 2:
                # 找阵容最弱的类别（同样按归一化值比较）
                weakest = min(
                    cat_totals.get(s, 0) / _CAT_TYPICAL_TOTAL.get(s, 1.0)
                    for s, _ in cat_values
                )
                strongest = max(
                    cat_totals.get(s, 0) / _CAT_TYPICAL_TOTAL.get(s, 1.0)
                    for s, _ in cat_values
                )
                if strongest > 0 and weakest < strongest * 0.5:
                    # 阵容偏科：给在弱类上有贡献的球员 bonus
                    for s, val in cat_values:
                        weakest_norm = cat_totals.get(s, 0) / _CAT_TYPICAL_TOTAL.get(s, 1.0)
                        if weakest_norm == weakest and val > 0:
                            bonus += val * 0.02  # 轻量 bonus

        return min(bonus, 15.0)  # 上限 15 分，避免压过 VORP

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
        """判断是否为价值股：ADP 远好于实际选中顺位（球员滑落到你手里）。

        修复审计高危项：旧实现 (adp - total_pick) > 阈值 方向相反——
        把「提前抢人（reach）」标成价值股，真正的滑落者反而不标。
        正确方向：total_pick - adp > 阈值。例：ADP=100 的球员在第 115
        顺位被选中（滑落 15 检）→ 价值股；第 85 顺位抢走 → reach，非价值股。
        """
        if not self.show_value_picks:
            return False
        adp = self._player_adp(name)
        return adp is not None and (total_pick - adp) > VALUE_PICK_THRESHOLD
