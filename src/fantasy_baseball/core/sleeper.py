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

from ..config import find_output_file, get_season, resolve_path
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
    season: Optional[int] = None,
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
    rankings = _load_rankings(rankings_file, season or get_season())
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
        _apply_statcast(candidates, statcast_batter_file, statcast_pitcher_file, season)

    # 排序：先按 statcast_strength 再按 bias
    candidates = candidates.sort_values(
        ["statcast_strength", "bias"], ascending=False
    ).head(top)
    return candidates.reset_index(drop=True)


def _load_rankings(rankings_file: Optional[str], season: int) -> pd.DataFrame:
    """加载排名 CSV；未提供则现算。"""
    if rankings_file is None:
        rankings_file = f"fantasy_draft_rankings_vorp_{season}.csv"
    path = find_output_file(rankings_file)
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
    season: Optional[int] = None,
) -> None:
    """对候选球员叠加 Statcast 信号（直接修改 candidates）。

    修复 M5：原实现读本地 CSV（data/statcast_batter_2025.csv 等，不存在），
    导致「启用Statcast增强」开关恒无效。现改为：
    1. 若用户提供了显式 CSV 文件（batter_file/pitcher_file），仍从文件读
    2. 否则通过 MLBStatsClient.search_player + StatcastFetcher 获取真实数据
       （两者都有 JSON 缓存，候选球员通常仅十几个，开销可控）
    """
    pos_col = "pos" if "pos" in candidates.columns else "pos_adp"

    # 显式文件路径优先（向后兼容手动 CSV 工作流）
    batter_df = _load_statcast(batter_file, None) if batter_file else None
    pitcher_df = _load_statcast(pitcher_file, None) if pitcher_file else None

    # 无文件时走真实 API（带缓存）
    if batter_df is None or pitcher_df is None:
        _apply_statcast_from_api(candidates, pos_col, season,
                                 need_batter=batter_df is None,
                                 need_pitcher=pitcher_df is None)

    # 处理显式 CSV 数据
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
        logger.info("Statcast 打者信号（CSV）：命中 %d 人", n)

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
        logger.info("Statcast 投手信号（CSV）：命中 %d 人", n)


def _apply_statcast_from_api(
    candidates: pd.DataFrame, pos_col: str, season: Optional[int],
    need_batter: bool, need_pitcher: bool,
) -> None:
    """通过 MLB API（带缓存）给候选球员叠加 Statcast 信号。"""
    try:
        from ..data_fetch.mlb_api import MLBStatsClient
        from ..data_fetch.statcast import StatcastFetcher
    except ImportError:
        logger.warning("数据抓取模块不可用，跳过 Statcast 增强")
        return

    if season is None:
        import datetime
        season = datetime.datetime.now().year - 1  # Statcast 用最近完整赛季

    client = MLBStatsClient()
    fetcher = StatcastFetcher()
    n = 0
    for idx, player in candidates.iterrows():
        pos = player.get(pos_col, "")
        is_hitter = pos in HITTER_POSITIONS
        if (is_hitter and not need_batter) or (not is_hitter and not need_pitcher):
            continue
        try:
            person = client.search_player(player["name"])
            if not person:
                continue
            mlb_id = person["id"]
            sc = (
                fetcher.fetch_hitter_data(mlb_id, season)
                if is_hitter else fetcher.fetch_pitcher_data(mlb_id, season)
            )
            if not sc:
                continue
            signals, strength = (
                _batter_signals_dict(sc) if is_hitter else _pitcher_signals_dict(sc)
            )
            if signals:
                candidates.at[idx, "statcast_signal"] = "; ".join(signals)
                candidates.at[idx, "statcast_strength"] = strength
                n += 1
        except Exception as e:
            logger.debug("Statcast 查询失败 (%s): %s", player.get("name"), e)
    logger.info("Statcast 信号（API）：命中 %d 人", n)


def _batter_signals_dict(sc: dict):
    """从 StatcastFetcher 返回的 dict 提取打者信号。"""
    signals: List[str] = []
    strength = 0
    xwoba = sc.get("xwOBA")
    avg = sc.get("AVG") or sc.get("avg")
    if _num(xwoba) and _num(avg) and xwoba >= 0.340 and avg < 0.250:
        signals.append("xwOBA ≥.340 但 AVG <.250（运气差）")
        strength += 2
    ev = sc.get("exit_velocity")
    br = sc.get("barrel_rate")
    if _num(ev) and _num(br) and ev >= 90 and br >= 0.08:
        signals.append("高 EV + 高桶率（硬核打者）")
        strength += 2
    return signals, strength


def _pitcher_signals_dict(sc: dict):
    """从 StatcastFetcher 返回的 dict 提取投手信号。"""
    signals: List[str] = []
    strength = 0
    xera = sc.get("xera", sc.get("xERA"))
    era = sc.get("ERA") or sc.get("era")
    if _num(xera) and _num(era) and xera <= 3.50 and era > xera + 0.5:
        signals.append("xERA ≤3.50 但 ERA 偏高（运气差）")
        strength += 2
    whiff = sc.get("whiff_rate")
    if _num(whiff) and whiff >= 0.30:
        signals.append("高三振挥空率（潜在三振红利）")
        strength += 1
    return signals, strength


def _load_statcast(explicit: Optional[str], default_rel: Optional[str]) -> Optional[pd.DataFrame]:
    """加载 Statcast CSV，规范化姓名为 "First Last"。返回 None 表示不可用。

    default_rel 为 None 时（未提供显式文件）直接返回 None，
    由调用方走 API 路径（修复 M5）。
    """
    path = resolve_path(explicit) if explicit else (
        resolve_path(default_rel) if default_rel else None
    )
    if path is None or not os.path.exists(path):
        logger.debug("Statcast 文件不存在或未提供: %s", path)
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
