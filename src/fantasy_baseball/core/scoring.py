"""统一的 VORP 与风险评分模型。

消除旧版三套 VORP 实现（fantasy_scoring_model_v2 / scoring/vorp_calculator /
fa_analyzer.fa_analyzer）的重复，以旧版 ``fantasy_scoring_model_v2`` 的 quantile
替代水平法为基础，结果与之保持一致。

算法：
- 打者：score = Σ(stat × weight)；按位置的 25 分位数为替代水平；vorp = score − replacement
- 投手：score = Σ(stat × weight)；全体的 25 分位数为替代水平；vorp = score − replacement
- 风险：z_score 法用 std ± adjustment；historical_variance 用比例缩放
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from ..config import get_config, resolve_path
from ..db import PlayerRepository, db_session
from ..utils.logger import get_logger

logger = get_logger("scoring")

# 默认输出列顺序
RANKING_COLUMNS = [
    "rank", "name", "team", "pos", "player_type",
    "vorp", "vorp_upside", "vorp_floor", "score",
]


class ScoringModel:
    """统一的球员评分与排名生成。"""

    def __init__(self, conn=None):
        """Args:
            conn: 可选的数据库连接。不传则每次计算时通过 db_session() 获取。
        """
        self._conn = conn
        cfg = get_config()
        self.scoring_rules = cfg["league"]["scoring"]
        self.risk_method = cfg["risk_model"]["method"]
        self.risk_adjustment = cfg["risk_model"]["adjustment_factor"]

    # ------------------------------------------------------------------ VORP
    def calculate_vorp(self) -> pd.DataFrame:
        """计算所有球员的 VORP 与风险评分，返回带 rank 的 DataFrame。"""
        logger.info("开始计算 VORP...")

        def _do(conn):
            repo = PlayerRepository(conn)
            hitters = repo.get_merged_hitters()
            pitchers = repo.get_merged_pitchers()
            if hitters.empty and pitchers.empty:
                raise ValueError("数据库中没有融合后的球员数据，请先运行数据导入")
            return hitters, pitchers

        hitters_df, pitchers_df = self._run(_do)

        if not hitters_df.empty:
            hitters_df = self._calculate_hitter_vorp(hitters_df.copy())
        if not pitchers_df.empty:
            pitchers_df = self._calculate_pitcher_vorp(pitchers_df.copy())

        all_df = pd.concat(
            [df for df in (hitters_df, pitchers_df) if not df.empty],
            ignore_index=True,
        )
        all_df = self._calculate_risk_scores(all_df)
        all_df = all_df.sort_values("vorp", ascending=False).reset_index(drop=True)
        all_df["rank"] = range(1, len(all_df) + 1)
        logger.info("VORP 计算完成，共 %d 名球员", len(all_df))
        return all_df

    def _calculate_hitter_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算打者 VORP（按位置 25 分位数为替代水平）。"""
        df["score"] = self._compute_score(df, self.scoring_rules["hitters"])

        replacement_levels = {}
        for pos in df["pos"].dropna().unique():
            pos_scores = df.loc[df["pos"] == pos, "score"]
            if len(pos_scores) > 0:
                replacement_levels[pos] = pos_scores.quantile(0.25)

        df["vorp"] = df.apply(
            lambda row: row["score"] - replacement_levels.get(row["pos"], 0), axis=1
        )
        df["player_type"] = "hitter"
        return df

    def _calculate_pitcher_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算投手 VORP（全体 25 分位数为替代水平）。"""
        df["score"] = self._compute_score(df, self.scoring_rules["pitchers"])
        replacement = df["score"].quantile(0.25)
        df["vorp"] = df["score"] - replacement
        df["player_type"] = "pitcher"
        return df

    @staticmethod
    def _compute_score(df: pd.DataFrame, weights: dict) -> pd.Series:
        """根据评分规则加权求和，忽略不存在的列。"""
        score = pd.Series(0.0, index=df.index)
        for stat, weight in weights.items():
            if stat in df.columns:
                score = score + pd.to_numeric(df[stat], errors="coerce").fillna(0) * weight
        return score

    # ------------------------------------------------------------------ 风险
    def _calculate_risk_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 vorp_upside / vorp_floor。"""
        if self.risk_method == "z_score":
            for ptype in ("hitter", "pitcher"):
                mask = df["player_type"] == ptype
                if mask.sum() > 1:
                    std = df.loc[mask, "vorp"].std()
                    if pd.isna(std):
                        std = 0
                    df.loc[mask, "vorp_upside"] = df.loc[mask, "vorp"] + std * self.risk_adjustment
                    df.loc[mask, "vorp_floor"] = df.loc[mask, "vorp"] - std * self.risk_adjustment
        elif self.risk_method == "historical_variance":
            df["vorp_upside"] = df["vorp"] * (1 + self.risk_adjustment)
            df["vorp_floor"] = df["vorp"] * (1 - self.risk_adjustment)
        else:
            df["vorp_upside"] = df["vorp"] * 1.1
            df["vorp_floor"] = df["vorp"] * 0.9

        # floor 不为负
        if "vorp_floor" in df.columns:
            df["vorp_floor"] = df["vorp_floor"].clip(lower=0)
        else:
            df["vorp_upside"] = df["vorp"]
            df["vorp_floor"] = df["vorp"].clip(lower=0)

        return df

    # -------------------------------------------------------------- 输出排名
    def generate_rankings(self, output_file: Optional[str] = None) -> str:
        """生成排名 CSV 文件，返回绝对路径。"""
        cfg = get_config()
        if output_file is None:
            output_file = "fantasy_draft_rankings_vorp_2026.csv"
        output_path = resolve_path(output_file)

        rankings = self.calculate_vorp()
        for col in RANKING_COLUMNS:
            if col not in rankings.columns:
                rankings[col] = None
        rankings = rankings[RANKING_COLUMNS]

        rankings.to_csv(output_path, index=False)
        logger.info("排名文件已保存: %s（%d 名球员）", output_path, len(rankings))
        if len(rankings) > 0:
            top = rankings.iloc[0]
            logger.info("排名第一: %s (VORP: %.2f)", top["name"], top["vorp"])
        return output_path

    # -------------------------------------------------------------- 内部工具
    def _run(self, func):
        """在自有连接或 db_session 中执行 func(conn)。"""
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
