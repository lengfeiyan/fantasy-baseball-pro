"""Statcast 数据抓取与聚合。

数据源：``baseballsavant.mlb.com`` 的 Statcast CSV 接口（免费、无需 key）。

返回逐投球原始数据（约 2.5 万行/球员/赛季），用 pandas 聚合成球员级指标：
- 打者：exit_velocity、launch_angle、barrel_rate、hard_hit_rate、xwoba
- 投手：whiff_rate、velocity、spin_rate、hard_hit_allowed_rate

依赖：标准库 urllib + 已有的 pandas。首次抓取较慢（几秒），结果缓存 JSON。
"""

from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, Optional

import pandas as pd

from ..config import resolve_path
from ..utils.logger import get_logger

logger = get_logger("data_fetch.statcast")

SAVANT_URL = "https://baseballsavant.mlb.com/statcast_search/csv"
_REQUEST_TIMEOUT = 45  # CSV 较大，超时放宽
_CACHE_TTL_HOURS = 24  # Statcast 聚合结果缓存 24 小时

# mock 兜底数据（真实数据不可用时返回，保证 FA 评分不为 0）
_MOCK_HITTER_STATCAST = {
    "exit_velocity": 88.5, "launch_angle": 12.0, "xwOBA": 0.330,
    "hard_hit_rate": 0.38, "barrel_rate": 0.07, "swing_contact_rate": 0.76,
}
_MOCK_PITCHER_STATCAST = {
    "velocity": 93.5, "spin_rate": 2300, "whiff_rate": 0.24,
    # xera 口径与真实聚合一致（面对打者 xwOBA×5.5 ≈ 1.8-2.2）；
    # 此前 4.20 是官方 xERA 量级，与真实数据差一个尺度
    "xera": 2.05, "hard_hit_allowed_rate": 0.38,
}


def _fetch_csv(url: str) -> Optional[pd.DataFrame]:
    """抓取 CSV 并解析为 DataFrame。失败返回 None。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        if not content.strip():
            return None
        return pd.read_csv(io.StringIO(content))
    except Exception as e:
        logger.warning("Statcast CSV 抓取失败: %s", e)
        return None


class StatcastFetcher:
    """Statcast 数据抓取器（带 JSON 缓存）。

    保留此类名以向后兼容（旧版 GUI 调用 StatcastFetcher）。
    """

    def __init__(self, cache_dir: Optional[str] = None, cache_ttl_hours: int = _CACHE_TTL_HOURS):
        self.cache_dir = resolve_path(cache_dir or "data/cache")
        self.cache_ttl = cache_ttl_hours * 3600
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_hitter_data(self, player_id: int, season: int = 2025) -> Dict[str, Any]:
        """获取打者 Statcast 聚合数据。

        Args:
            player_id: MLB player_id。
            season: 赛季年份。
        """
        cache_key = f"sc_hitter_{player_id}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{SAVANT_URL}?all=true&type=details&player_type=batter"
            f"&players_lookup={player_id}&season={season}&min_pa=1"
        )
        df = _fetch_csv(url)
        if df is None or df.empty:
            logger.info("Statcast 不可用 (player_id=%d)，使用 mock 兜底", player_id)
            return dict(_MOCK_HITTER_STATCAST, player_id=player_id, type="hitter", season=season)

        result = _aggregate_hitter(df, player_id)
        result["season"] = season
        self._save_cache(cache_key, result)
        return result

    def fetch_pitcher_data(self, player_id: int, season: int = 2025) -> Dict[str, Any]:
        """获取投手 Statcast 聚合数据。"""
        cache_key = f"sc_pitcher_{player_id}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{SAVANT_URL}?all=true&type=details&player_type=pitcher"
            f"&players_lookup={player_id}&season={season}&min_pa=1"
        )
        df = _fetch_csv(url)
        if df is None or df.empty:
            logger.info("Statcast 不可用 (player_id=%d)，使用 mock 兜底", player_id)
            return dict(_MOCK_PITCHER_STATCAST, player_id=player_id, type="pitcher", season=season)

        result = _aggregate_pitcher(df, player_id)
        result["season"] = season
        self._save_cache(cache_key, result)
        return result

    # -------------------------------------------------------------- 缓存
    def _cache_file(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def _load_cache(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._cache_file(key)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.cache_ttl:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cache(self, key: str, data: Dict[str, Any]) -> None:
        try:
            with open(self._cache_file(key), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("写入 Statcast 缓存失败: %s", e)


# -------------------------------------------------------------- 聚合逻辑
def _aggregate_hitter(df: pd.DataFrame, player_id: int) -> Dict[str, Any]:
    """聚合打者 Statcast。只统计实际打进球（launch_speed 非空）。"""
    # 列名规范化（CSV 列可能有 BOM）
    df = df.rename(columns={c: c.strip().lstrip("\ufeff") for c in df.columns})

    result: Dict[str, Any] = {"player_id": player_id, "type": "hitter"}

    # 只看有 exit velocity 的打进球
    if "launch_speed" not in df.columns:
        return result
    batted = df[df["launch_speed"].notna()].copy()
    if batted.empty:
        return result

    result["exit_velocity"] = round(float(batted["launch_speed"].mean()), 2)
    if "launch_angle" in batted.columns:
        result["launch_angle"] = round(float(batted["launch_angle"].mean()), 2)

    # launch_speed_angle: 1-6 档，>=5 为 hard hit，6 为 barrel
    if "launch_speed_angle" in batted.columns:
        lsa = batted["launch_speed_angle"].dropna()
        if not lsa.empty:
            result["hard_hit_rate"] = round(float((lsa >= 5).mean()), 3)
            result["barrel_rate"] = round(float((lsa == 6).mean()), 3)

    # xwOBA（基于速度角度的估算）
    if "estimated_woba_using_speedangle" in batted.columns:
        xwoba = batted["estimated_woba_using_speedangle"].dropna()
        if not xwoba.empty:
            result["xwOBA"] = round(float(xwoba.mean()), 3)

    # swing_contact_rate: 简化为打进球 / (打进球 + 三振)
    if "events" in df.columns:
        total_events = df["events"].dropna()
        so = (total_events == "strikeout").sum()
        result["swing_contact_rate"] = round(
            len(batted) / (len(batted) + so) if (len(batted) + so) > 0 else 0, 3
        )

    return result


def _aggregate_pitcher(df: pd.DataFrame, player_id: int) -> Dict[str, Any]:
    """聚合投手 Statcast。"""
    df = df.rename(columns={c: c.strip().lstrip("\ufeff") for c in df.columns})

    result: Dict[str, Any] = {"player_id": player_id, "type": "pitcher"}

    # 球速
    if "release_speed" in df.columns:
        speeds = df["release_speed"].dropna()
        if not speeds.empty:
            result["velocity"] = round(float(speeds.mean()), 1)

    # 转速
    if "release_spin_rate" in df.columns:
        spin = df["release_spin_rate"].dropna()
        if not spin.empty:
            result["spin_rate"] = round(float(spin.mean()), 0)

    # whiff rate: description 含 "swinging_strike"
    if "description" in df.columns:
        desc = df["description"].fillna("")
        swings = desc[desc.isin(["hit_into_play", "foul", "swinging_strike", "swinging_strike_blocked"])]
        whiffs = (desc == "swinging_strike").sum() + (desc == "swinging_strike_blocked").sum()
        if len(swings) > 0:
            result["whiff_rate"] = round(whiffs / len(swings), 3)

    # xERA（投手面对的打者 xwOBA 反推）
    if "estimated_woba_using_speedangle" in df.columns:
        xwoba = df["estimated_woba_using_speedangle"].dropna()
        if not xwoba.empty:
            # xERA 近似: xwOBA 越低越好，粗略映射
            result["xera"] = round(float(xwoba.mean()) * 5.5, 2)  # 粗略近似

    # hard hit allowed rate
    if "launch_speed_angle" in df.columns:
        lsa = df["launch_speed_angle"].dropna()
        if not lsa.empty:
            result["hard_hit_allowed_rate"] = round(float((lsa >= 5).mean()), 3)

    return result
