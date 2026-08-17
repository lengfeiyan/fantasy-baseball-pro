"""Standings Gain Points（SGP）评分模型。

与 VORP 并行的另一种评分体系，专为 5×5 Roto 联盟设计。

核心思想：计算每个球员在**每个统计类别**上能让你"升几名"（standings points），
再求和得到总价值。相比 VORP 的线性加权，SGP 能正确处理比率统计（AVG/ERA/WHIP），
因为比率统计按"球员对团队均值的实际拉动"而非原始小数值计算。

参考：[Smart Fantasy Baseball](https://www.smartfantasybaseball.com/2013/03/create-your-own-fantasy-baseball-rankings-part-5-understanding-standings-gain-points/)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..config import get_config, get_season, output_path
from ..db import PlayerRepository, db_session
from ..utils.logger import get_logger

logger = get_logger("sgp")

# 12 队联盟的 SGP 分母经验值（来自 Razzball / Smart Fantasy Baseball）
DEFAULT_HITTER_DENOMS = {
    "R": 24.6, "HR": 10.4, "RBI": 24.6, "SB": 9.4, "AVG": 0.0024,
}
DEFAULT_PITCHER_DENOMS = {
    "W": 3.03, "SV": 9.95, "K": 39.3, "ERA": -0.076, "WHIP": -0.015,
}

# 比率统计的"假想团队基准"（14 打者 / 9 投手的 12 队联盟经验值）
# AVG：团队 .267 = 1768 H / 6617 AB
_TEAM_AVG_H = 1768.0
_TEAM_AVG_AB = 6617.0
_TEAM_AVG = 0.267
# ERA：团队 3.59 = 475 ER / 1192 IP
_TEAM_ER = 475.0
_TEAM_IP = 1192.0
_TEAM_ERA = 3.59
# WHIP：团队 1.23 = 1466 (BB+H) / 1192 IP
_TEAM_WHIP_BASE = 1466.0
_TEAM_WHIP = 1.23


class SGPModel:
    """Standings Gain Points 评分模型。

    与 ``ScoringModel``（VORP）并行，可独立或同时使用。
    """

    def __init__(self, conn=None):
        self._conn = conn
        cfg = get_config()
        sgp_cfg = cfg.get("sgp", {})
        league_size = cfg["league"]["size"]
        # SGP 分母按联盟规模线性缩放（经验值基于 12 队）
        # 队伍越多，每个类别总量越大，升一名需要的统计量越多（分母越大）
        scale = league_size / 12.0

        base_hitter = {
            **DEFAULT_HITTER_DENOMS,
            **sgp_cfg.get("denominators", {}).get("hitters", {}),
        }
        base_pitcher = {
            **DEFAULT_PITCHER_DENOMS,
            **sgp_cfg.get("denominators", {}).get("pitchers", {}),
        }
        # 计数统计的分母直接缩放；比率统计的分母（AVG/ERA/WHIP）不缩放（与队伍数无关）
        self.hitter_denoms = {
            k: (v * scale if k in ("R", "HR", "RBI", "SB") else v)
            for k, v in base_hitter.items()
        }
        self.pitcher_denoms = {
            k: (v * scale if k in ("W", "SV", "K") else v)
            for k, v in base_pitcher.items()
        }
        # 替代水平：取联盟规模 × 选秀轮数之后的球员
        self.replacement_cutoff = league_size * cfg["league"]["rounds"]

    # -------------------------------------------------------------- 主入口
    def calculate_sgp(self) -> pd.DataFrame:
        """计算所有球员的 SGP，返回带 sgp_total 和 rank 的 DataFrame。"""
        logger.info("开始计算 SGP...")

        def _do(conn):
            repo = PlayerRepository(conn)
            hitters = repo.get_merged_hitters()
            pitchers = repo.get_merged_pitchers()
            if hitters.empty and pitchers.empty:
                raise ValueError("数据库中没有融合后的球员数据")
            return hitters, pitchers

        hitters_df, pitchers_df = self._run(_do)

        if not hitters_df.empty:
            hitters_df = self._calc_hitter_sgp(hitters_df.copy())
        if not pitchers_df.empty:
            pitchers_df = self._calc_pitcher_sgp(pitchers_df.copy())

        all_df = pd.concat(
            [df for df in (hitters_df, pitchers_df) if not df.empty],
            ignore_index=True,
        )

        # 替代水平调整：减去"最后一个被选"球员的 SGP
        all_df = all_df.sort_values("sgp_total", ascending=False).reset_index(drop=True)
        cutoff_idx = min(self.replacement_cutoff, len(all_df) - 1)
        if cutoff_idx > 0 and len(all_df) > cutoff_idx:
            replacement_sgp = all_df.loc[cutoff_idx, "sgp_total"]
            all_df["sgp_total"] = all_df["sgp_total"] - replacement_sgp

        all_df = all_df.sort_values("sgp_total", ascending=False).reset_index(drop=True)
        all_df["sgp_rank"] = range(1, len(all_df) + 1)
        logger.info("SGP 计算完成，共 %d 名球员", len(all_df))
        return all_df

    # -------------------------------------------------------------- 打者 SGP
    def _calc_hitter_sgp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算打者 5 类 SGP（R/HR/RBI/SB/AVG）。"""
        d = self.hitter_denoms

        # 计数统计：直接除分母
        df["sgp_R"] = pd.to_numeric(df.get("R"), errors="coerce").fillna(0) / d["R"]
        df["sgp_HR"] = pd.to_numeric(df.get("HR"), errors="coerce").fillna(0) / d["HR"]
        df["sgp_RBI"] = pd.to_numeric(df.get("RBI"), errors="coerce").fillna(0) / d["RBI"]
        df["sgp_SB"] = pd.to_numeric(df.get("SB"), errors="coerce").fillna(0) / d["SB"]

        # 比率统计 AVG：球员对团队均值的拉动
        ab = pd.to_numeric(df.get("AB"), errors="coerce").fillna(0)
        h = pd.to_numeric(df.get("H"), errors="coerce").fillna(0)
        team_new_avg = (h + _TEAM_AVG_H) / (ab + _TEAM_AVG_AB)
        df["sgp_AVG"] = (team_new_avg - _TEAM_AVG) / d["AVG"]

        df["sgp_total"] = df["sgp_R"] + df["sgp_HR"] + df["sgp_RBI"] + df["sgp_SB"] + df["sgp_AVG"]
        df["player_type"] = "hitter"
        return df

    # -------------------------------------------------------------- 投手 SGP
    def _calc_pitcher_sgp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算投手 5 类 SGP（W/SV/K/ERA/WHIP）。"""
        d = self.pitcher_denoms

        df["sgp_W"] = pd.to_numeric(df.get("W"), errors="coerce").fillna(0) / d["W"]
        df["sgp_SV"] = pd.to_numeric(df.get("SV"), errors="coerce").fillna(0) / d["SV"]
        df["sgp_K"] = pd.to_numeric(df.get("K"), errors="coerce").fillna(0) / d["K"]

        # ERA：球员对团队 ERA 的拉动（越低越好，分母为负）
        er = pd.to_numeric(df.get("ER"), errors="coerce").fillna(0)
        ip = pd.to_numeric(df.get("IP"), errors="coerce").replace(0, np.nan)
        team_new_era = (er + _TEAM_ER) * 9 / (ip + _TEAM_IP)
        df["sgp_ERA"] = (team_new_era - _TEAM_ERA) / d["ERA"]

        # WHIP：球员对团队 WHIP 的拉动
        h_allow = pd.to_numeric(df.get("H_allow"), errors="coerce").fillna(0)
        bb_allow = pd.to_numeric(df.get("BB_allow"), errors="coerce").fillna(0)
        team_new_whip = (h_allow + bb_allow + _TEAM_WHIP_BASE) / (ip + _TEAM_IP)
        df["sgp_WHIP"] = (team_new_whip - _TEAM_WHIP) / d["WHIP"]

        df["sgp_total"] = df["sgp_W"] + df["sgp_SV"] + df["sgp_K"] + df["sgp_ERA"].fillna(0) + df["sgp_WHIP"].fillna(0)
        df["player_type"] = "pitcher"
        return df

    # -------------------------------------------------------------- 生成排名
    def generate_rankings(self, output_file: Optional[str] = None) -> str:
        """生成 SGP 排名 CSV，返回路径。"""
        if output_file is None:
            # 修复 H7：文件名跟随生效赛季，不再硬编码 2026
            output_file = f"fantasy_draft_rankings_sgp_{get_season()}.csv"
        path = output_path(output_file)

        df = self.calculate_sgp()
        # 保留关键列
        keep = ["sgp_rank", "name", "team", "pos", "player_type", "sgp_total"]
        keep += [c for c in ["sgp_R", "sgp_HR", "sgp_RBI", "sgp_SB", "sgp_AVG",
                             "sgp_W", "sgp_SV", "sgp_K", "sgp_ERA", "sgp_WHIP"]
                 if c in df.columns]
        df[[c for c in keep if c in df.columns]].to_csv(path, index=False)
        logger.info("SGP 排名已保存: %s", path)
        return path

    # -------------------------------------------------------------- 内部
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
