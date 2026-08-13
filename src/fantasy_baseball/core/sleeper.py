"""Sleeper 推荐：发现被市场低估的高潜力球员。

合并旧版 ``find_sleeper_players.py``（v1）与 ``find_sleeper_players_statcast_v2.0.py``
（v2）。statcast 增强作为可选参数开关：开启时融合 Statcast 信号，关闭时退化为
v1 的纯 VORP-vs-ADP 偏差逻辑。

修复旧版 bug：``generate_report`` 引用全局 ``args``；新版所有参数显式传入。
"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd

from ..config import resolve_path
from ..utils.logger import get_logger
from .adp import get_adp
from .scoring import ScoringModel

logger = get_logger("sleeper")

HITTER_POSITIONS = {"C", "1B", "2B", "3B", "SS", "OF", "UTIL"}


def find_sleepers(
    *,
    rankings_file: Optional[str] = None,
    adp_file: Optional[str] = None,
    statcast_batter_file: Optional[str] = None,
    statcast_pitcher_file: Optional[str] = None,
    min_adp: int = 80,
    max_adp: int = 300,
    min_bias: int = 30,
    position: Optional[str] = None,
    top: int = 15,
    use_statcast: bool = True,
) -> pd.DataFrame:
    """寻找被低估的球员。

    Args:
        rankings_file: 排名 CSV 路径。None 则自动生成。
        adp_file: ADP CSV 路径。None 则用缓存。
        statcast_batter_file / statcast_pitcher_file: Statcast CSV（可选）。
        min_adp / max_adp: ADP 区间筛选。
        min_bias: 最小低估顺位（adp − expected_pick）。
        position: 仅筛选该位置。None 表示全部。
        top: 返回前 N 个。
        use_statcast: 是否融合 Statcast 信号。

    Returns:
        筛选后的 DataFrame，含 bias / statcast_signal / statcast_strength 列。
    """
    rankings = _load_rankings(rankings_file)
    adp = _load_adp(adp_file)

    # 合并排名与 ADP
    merged = pd.merge(rankings, adp, on="name", how="inner", suffixes=("", "_adp"))
    if "pos_adp" in merged.columns and "pos" not in merged.columns:
        merged = merged.rename(columns={"pos_adp": "pos"})

    # 计算预期顺位与低估程度
    merged["expected_pick"] = merged["vorp"].rank(ascending=False).astype(int)
    merged["bias"] = merged["adp"] - merged["expected_pick"]

    # 基础筛选
    mask = (merged["adp"] >= min_adp) & (merged["adp"] <= max_adp) & (merged["bias"] >= min_bias)
    if position:
        pos_col = "pos" if "pos" in merged.columns else "pos_adp"
        mask &= merged[pos_col] == position

    candidates = merged[mask].copy()
    logger.info("基础筛选后 %d 个候选球员", len(candidates))

    # Statcast 增强（可选）
    candidates["statcast_signal"] = ""
    candidates["statcast_strength"] = 0
    if use_statcast:
        _apply_statcast(candidates, statcast_batter_file, statcast_pitcher_file)

    # 排序：先按 statcast_strength 再按 bias
    candidates = candidates.sort_values(
        ["statcast_strength", "bias"], ascending=False
    ).head(top)
    return candidates.reset_index(drop=True)


def _load_rankings(rankings_file: Optional[str]) -> pd.DataFrame:
    """加载排名 CSV；未提供则现算。"""
    if rankings_file is None:
        rankings_file = "fantasy_draft_rankings_vorp_2026.csv"
    path = resolve_path(rankings_file)
    if os.path.exists(path):
        return pd.read_csv(path)
    logger.info("排名文件不存在，现算中: %s", path)
    ScoringModel().generate_rankings(rankings_file)
    return pd.read_csv(path)


def _load_adp(adp_file: Optional[str]) -> pd.DataFrame:
    return get_adp() if adp_file is None else pd.read_csv(resolve_path(adp_file))


def _apply_statcast(
    candidates: pd.DataFrame,
    batter_file: Optional[str],
    pitcher_file: Optional[str],
) -> None:
    """对候选球员叠加 Statcast 信号（直接修改 candidates）。"""
    pos_col = "pos" if "pos" in candidates.columns else "pos_adp"

    # 打者 Statcast
    batter_df = _load_statcast(batter_file, "data/statcast_batter_2025.csv")
    if batter_df is not None:
        n = 0
        for idx, player in candidates[candidates[pos_col].isin(HITTER_POSITIONS)].iterrows():
            row = batter_df[batter_df["name"] == player["name"]]
            if row.empty:
                continue
            signals, strength = _batter_signals(row.iloc[0])
            if signals:
                candidates.at[idx, "statcast_signal"] = "; ".join(signals)
                candidates.at[idx, "statcast_strength"] = strength
                n += 1
        logger.info("Statcast 打者信号：命中 %d 人", n)

    # 投手 Statcast
    pitcher_df = _load_statcast(pitcher_file, "data/statcast_pitcher_2025.csv")
    if pitcher_df is not None:
        n = 0
        for idx, player in candidates[candidates[pos_col].isin({"SP", "RP"})].iterrows():
            row = pitcher_df[pitcher_df["name"] == player["name"]]
            if row.empty:
                continue
            signals, strength = _pitcher_signals(row.iloc[0])
            if signals:
                candidates.at[idx, "statcast_signal"] = "; ".join(signals)
                candidates.at[idx, "statcast_strength"] = strength
                n += 1
        logger.info("Statcast 投手信号：命中 %d 人", n)


def _load_statcast(explicit: Optional[str], default_rel: str) -> Optional[pd.DataFrame]:
    """加载 Statcast CSV，规范化姓名为 "First Last"。返回 None 表示不可用。"""
    path = resolve_path(explicit) if explicit else resolve_path(default_rel)
    if not os.path.exists(path):
        logger.debug("Statcast 文件不存在: %s", path)
        return None
    try:
        df = pd.read_csv(path)
    except Exception as e:
        logger.warning("读取 Statcast 失败: %s", e)
        return None
    # Baseball Savant 用 Last, First；规范化
    if "First Name" in df.columns and "Last Name" in df.columns:
        df["name"] = df["First Name"].astype(str) + " " + df["Last Name"].astype(str)
    elif "name" not in df.columns:
        df["name"] = ""
    return df


def _batter_signals(b: pd.Series):
    """提取打者 Statcast 信号。返回 (信号描述列表, 强度)。"""
    signals: List[str] = []
    strength = 0
    xwoba = b.get("xwOBA")
    avg = b.get("AVG")
    if _num(xwoba) and _num(avg) and xwoba >= 0.340 and avg < 0.250:
        signals.append("xwOBA ≥.340 但 AVG <.250（运气差）")
        strength += 2
    ev = b.get("exit_velocity", b.get("Exit Velocity"))
    br = b.get("barrel%", b.get("Barrel %"))
    if _num(ev) and _num(br) and ev >= 90 and br >= 8:
        signals.append("高 EV + 高桶率（硬核打者）")
        strength += 2
    return signals, strength


def _pitcher_signals(p: pd.Series):
    """提取投手 Statcast 信号。"""
    signals: List[str] = []
    strength = 0
    xera = p.get("xERA")
    era = p.get("ERA")
    if _num(xera) and _num(era) and xera <= 3.50 and era > xera + 0.5:
        signals.append("xERA ≤3.50 但 ERA 偏高（运气差）")
        strength += 2
    whiff = p.get("whiff%", p.get("Whiff %"))
    if _num(whiff) and whiff >= 30:
        signals.append("高三振挥空率（潜在三振红利）")
        strength += 1
    return signals, strength


def _num(v) -> bool:
    """判断值是否为可用数值（非 None、非 NaN）。"""
    try:
        return v is not None and not pd.isna(v)
    except (TypeError, ValueError):
        return False
