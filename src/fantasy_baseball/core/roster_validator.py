"""阵容验证器。

迁移自旧版 ``validate_roster.py``，修复了 ``analyze_roster_strength`` 中
"打者/投手 VORP 比例"在投手为 0 时的除零 bug。验证结果以结构化数据返回，
打印逻辑分离，便于 GUI 与 CLI 复用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from ..config import find_output_file, get_config
from ..utils.logger import get_logger

logger = get_logger("roster_validator")

HITTER_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "UTIL"}
PITCHER_POSITIONS = {"SP", "RP"}


@dataclass
class ValidationResult:
    """阵容验证结果。"""
    is_valid: bool
    pos_counts: Dict[str, int]
    slot_requirements: Dict[str, int]
    issues: List[str] = field(default_factory=list)  # 每个位置的不足/超编描述
    suggestions: List[str] = field(default_factory=list)


@dataclass
class StrengthResult:
    """阵容强度分析结果。"""
    total_vorp: float
    avg_vorp: float
    hitters_vorp: float
    pitchers_vorp: float
    hitter_pitcher_ratio: Optional[float]  # 投手为0时为 None
    round_quality: List[Dict[str, float]]
    best_pick: Optional[pd.Series]
    worst_pick: Optional[pd.Series]


class RosterValidator:
    """阵容合规性与强度分析。"""

    def __init__(self):
        cfg = get_config()
        self.roster_slots = cfg["league"]["roster_slots"]

    @staticmethod
    def _filter_user_team(
        draft_log: pd.DataFrame, team_id: Optional[int]
    ) -> pd.DataFrame:
        """从（可能是全联盟的）选秀日志中提取用户单队阵容。

        修复审计高危项：旧实现拿完整选秀日志（12 队 × 15 轮 ≈ 180 行）直接
        统计位置计数并对照**单队**槽位，结果恒为「超编几十人」；
        强度分析同样是全联盟口径而非用户 15 人阵容。

        提取优先级：显式 team_id 参数 → ``is_user_pick`` 列 → 原样返回
        （视为单队日志，兼容手动裁剪/旧格式日志）。
        """
        if team_id is not None and "team" in draft_log.columns:
            return draft_log[draft_log["team"] == team_id]
        if "is_user_pick" in draft_log.columns:
            user_df = draft_log[draft_log["is_user_pick"] == True]  # noqa: E712
            if not user_df.empty:
                return user_df
        return draft_log

    def validate_roster(
        self, draft_log_file: str, team_id: Optional[int] = None
    ) -> ValidationResult:
        """验证选秀日志中的阵容是否合规。

        Args:
            draft_log_file: 选秀日志 CSV 路径。全联盟日志会自动按
                ``is_user_pick`` 列过滤出用户单队（也可用 team_id 显式指定）。
            team_id: 用户球队编号（日志 team 列的值），None 则自动识别。
        """
        draft_log = self._load(draft_log_file)
        if draft_log is None:
            return ValidationResult(
                is_valid=False,
                pos_counts={},
                slot_requirements=self.roster_slots,
                issues=["无法读取选秀日志文件"],
            )

        draft_log = self._filter_user_team(draft_log, team_id)
        pos_counts = draft_log["pos"].value_counts().to_dict()
        issues: List[str] = []
        suggestions: List[str] = []

        for pos, max_count in self.roster_slots.items():
            current = pos_counts.get(pos, 0)
            if current < max_count:
                issues.append(f"{pos}: {current}/{max_count} → 缺少 {max_count - current} 个")
                suggestions.append(f"建议选择 {max_count - current} 个 {pos} 位置的球员")
            elif current > max_count:
                issues.append(f"{pos}: {current}/{max_count} → 超出 {current - max_count} 个")
                suggestions.append(f"建议减少 {current - max_count} 个 {pos} 位置的球员")

        # UTIL 槽位建议：把超编位置的球员移到 UTIL
        util_max = self.roster_slots.get("UTIL", 0)
        if util_max > 0 and pos_counts.get("UTIL", 0) < util_max:
            movable = draft_log[
                (draft_log["pos"] != "UTIL")
                & draft_log["pos"].map(lambda p: pos_counts.get(p, 0) > self.roster_slots.get(p, 0))
            ]
            if not movable.empty:
                suggestions.append(f"建议将 {movable.iloc[0]['name']} 移至 UTIL 位置")

        return ValidationResult(
            is_valid=len(issues) == 0,
            pos_counts=pos_counts,
            slot_requirements=self.roster_slots,
            issues=issues,
            suggestions=suggestions,
        )

    def analyze_roster_strength(
        self, draft_log_file: str, team_id: Optional[int] = None
    ) -> Optional[StrengthResult]:
        """分析阵容强度（修复旧版除零 bug、L4 的 vorp 全 0、以及全联盟口径）。

        Args:
            draft_log_file: 选秀日志 CSV 路径（全联盟日志自动过滤出用户单队）。
            team_id: 用户球队编号，None 则按 ``is_user_pick`` 列自动识别。
        """
        draft_log = self._load(draft_log_file)
        if draft_log is None or "vorp" not in draft_log.columns:
            return None
        draft_log = self._filter_user_team(draft_log, team_id)

        # 修复 L4：旧版 SGP 日志 vorp 列全 0，改用 sgp_total 计算强度
        value_col = "vorp"
        if (
            "sgp_total" in draft_log.columns
            and float(draft_log["vorp"].sum()) == 0
            and float(draft_log["sgp_total"].sum()) != 0
        ):
            value_col = "sgp_total"

        total_vorp = float(draft_log[value_col].sum())
        avg_vorp = float(draft_log[value_col].mean())

        hitters_vorp = float(
            draft_log.loc[draft_log["pos"].isin(HITTER_POSITIONS), value_col].sum()
        )
        pitchers_vorp = float(
            draft_log.loc[draft_log["pos"].isin(PITCHER_POSITIONS), value_col].sum()
        )
        # 修复除零 bug
        ratio = (hitters_vorp / pitchers_vorp) if pitchers_vorp != 0 else None

        round_quality = []
        if "round" in draft_log.columns:
            for rnd in sorted(draft_log["round"].unique()):
                picks = draft_log[draft_log["round"] == rnd]
                round_quality.append({
                    "round": int(rnd),
                    "total_vorp": float(picks[value_col].sum()),
                    "avg_vorp": float(picks[value_col].mean()),
                    "count": len(picks),
                })

        best_pick = draft_log.loc[draft_log[value_col].idxmax()] if len(draft_log) else None
        worst_pick = draft_log.loc[draft_log[value_col].idxmin()] if len(draft_log) else None

        return StrengthResult(
            total_vorp=total_vorp,
            avg_vorp=avg_vorp,
            hitters_vorp=hitters_vorp,
            pitchers_vorp=pitchers_vorp,
            hitter_pitcher_ratio=ratio,
            round_quality=round_quality,
            best_pick=best_pick,
            worst_pick=worst_pick,
        )

    @staticmethod
    def _load(draft_log_file: str) -> Optional[pd.DataFrame]:
        """加载选秀日志 CSV（优先 output/ 目录，其次项目根）。"""
        path = find_output_file(draft_log_file)
        if not os.path.exists(path):
            logger.error("选秀日志文件不存在: %s", path)
            return None
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.error("读取选秀日志失败: %s", e)
            return None
