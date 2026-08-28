"""Baseball Savant 排行榜快照（S1/S2 数据源）。

排行榜 CSV 端点（2026-08 实测可用）::

    https://baseballsavant.mlb.com/leaderboard/<board>?type=<batter|pitcher>&year=<Y>&team=&csv=true

覆盖：
- percentile-rankings  百分位（S1：FA 评分基准归一）
- expected_statistics  期望统计 vs 实际（S2：运气指数）

设计要点：
- 全联盟一张快照（~40-60KB CSV），替代逐球员查询，快几个量级
- 快照按 (board, type, year) 整包 JSON 缓存，TTL 默认 7 天
  （排行榜日更新，周级新鲜度足够评分用；force=True 强刷）
- 姓名规范化：Savant 用 "Last, First"，统一转为 "First Last"
  （与 FantasyPros / MLB API 对齐，便于跨源匹配）
- 任何失败返回 None（上层自行降级，不中断评分链路）
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from ..config import get_config, get_season, resolve_path
from ..utils.logger import get_logger

logger = get_logger("data_fetch.savant")

_BASE = "https://baseballsavant.mlb.com/leaderboard"
_DEFAULT_TTL_HOURS = 7 * 24  # 排行榜快照：7 天

_VALID_BOARDS = {"percentile-rankings", "expected_statistics"}
_VALID_TYPES = {"batter", "pitcher"}


def _normalize_name(raw: str) -> str:
    """"Last, First" → "First Last"；多余空白压缩。已是正序则原样规范化。"""
    raw = str(raw).strip()
    if not raw:
        return ""
    if "," in raw:
        last, _, first = raw.partition(",")
        raw = f"{first} {last}"
    return " ".join(raw.split())


class SavantLeaderboard:
    """Savant 排行榜 CSV 快照抓取与缓存。"""

    def __init__(self, cache_dir: Optional[str] = None, cache_ttl_hours: int = _DEFAULT_TTL_HOURS):
        cfg = get_config()
        self.cache_dir = resolve_path(
            cache_dir or cfg.get("fa_analyzer", {}).get("cache", {}).get("directory", "data/cache")
        )
        self.cache_ttl = cache_ttl_hours * 3600
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except OSError:
            pass

    # -------------------------------------------------------------- 公开 API
    def fetch_percentiles(self, player_type: str, season: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """百分位排行榜（S1）。

        Returns:
            行列表，每行含 name/player_id + 各指标百分位（0-100 整数）。
            打者：xwoba/xba/xslg/brl_percent/exit_velocity/hard_hit_percent/
                  k_percent/bb_percent/whiff_percent/chase_percent/sprint_speed/bat_speed...
            投手：xwoba(面对)/xera/whiff_percent/k_percent/bb_percent/fb_velocity/fb_spin...
            失败返回 None。
        """
        rows = self._fetch("percentile-rankings", player_type, season)
        return rows

    def fetch_expected_stats(self, player_type: str, season: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """期望统计排行榜（S2）。

        Returns:
            行列表，含 name/player_id + ba/est_ba/est_ba_minus_ba_diff/
            slg/est_slg/est_slg_minus_slg_diff/woba/est_woba/...（投手另有 era/xera）。
            差值为正 = 实际好于期望（状态虚高，卖出信号）。
            失败返回 None。
        """
        return self._fetch("expected_statistics", player_type, season)

    # -------------------------------------------------------------- 内部
    def _fetch(self, board: str, player_type: str, season: Optional[int]) -> Optional[List[Dict[str, Any]]]:
        if board not in _VALID_BOARDS or player_type not in _VALID_TYPES:
            raise ValueError(f"非法参数: board={board}, type={player_type}")
        season = season or (get_season() - 1)  # Statcast 类数据用最近完整赛季

        cache_key = f"savant_{board}_{player_type}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{_BASE}/{board}?type={player_type}&year={season}&team=&csv=true"
        logger.info("抓取 Savant 排行榜: %s", url)
        text = self._http_get_text(url)
        if not text or "player_name" not in text and "last_name" not in text:
            logger.warning("Savant 排行榜抓取失败或格式异常: %s", board)
            return None

        rows = self._parse_csv(text)
        if not rows:
            logger.warning("Savant 排行榜解析为空: %s", board)
            return None
        logger.info("Savant %s(%s, %d) 解析 %d 行", board, player_type, season, len(rows))

        self._save_cache(cache_key, rows)
        return rows

    @staticmethod
    def _http_get_text(url: str, timeout: int = 30) -> Optional[str]:
        import urllib.request

        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8-sig", errors="replace")
        except Exception as e:
            logger.warning("请求 Savant 失败: %s", e)
            return None

    @staticmethod
    def _parse_csv(text: str) -> List[Dict[str, Any]]:
        """解析 CSV，规范化姓名并做数值清洗。"""
        reader = csv.DictReader(io.StringIO(text))
        rows: List[Dict[str, Any]] = []
        for r in reader:
            r = {k.strip(): v for k, v in r.items() if k}
            # 姓名列兼容两种表头
            raw_name = r.pop("player_name", None) or r.pop("last_name, first_name", "") or r.pop("last_name", "")
            name = _normalize_name(raw_name)
            if not name:
                continue
            row: Dict[str, Any] = {"name": name}
            for k, v in r.items():
                row[k] = _num(v)
            rows.append(row)
        return rows

    # -------------------------------------------------------------- 缓存
    def _cache_file(self, key: str) -> str:
        safe = re.sub(r"[^\w\-]", "_", key)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _load_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
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

    def _save_cache(self, key: str, data: List[Dict[str, Any]]) -> None:
        try:
            with open(self._cache_file(key), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            logger.warning("写入 Savant 缓存失败: %s", e)


def _num(v) -> Optional[float]:
    """CSV 数值清洗：空串/'-'/非法 → None。"""
    if v is None:
        return None
    s = str(v).strip().rstrip("%").strip()
    if s in ("", "-", "--", "None", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return s  # 保留原始字符串（如位置缩写）
