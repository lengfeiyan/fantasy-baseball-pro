"""Savant 小联盟/春训 Statcast 聚合快照（F7 新秀雷达 Tier B/D 数据源）。

端点考古结论（2026-09 实测）：
- MiLB 聚合查询（整级一批，返回每名球员一行的聚合统计）::

    https://baseballsavant.mlb.com/statcast-search-minors/csv
        ?all=true&player_type=<batter|pitcher>&season=<Y>&minors=true&wbc=false

  关键参数语义（逐条实测验证）：
  * ``all=true`` 与 ``player_id=...`` 互斥——同给时 player_id 被忽略，
    返回默认时间窗的全联盟逐球数据（巨大且无意义），务必只给其一
  * 赛季参数是 ``season`` 单数
  * ``level`` 参数被服务端忽略（level=AAA / A / 不带，返回完全相同的行集）——
    批量结果本身就是「全部有公开 tracking 的小联盟球员」（AAA + Single-A/FSL）
- 公开 tracking 覆盖面：AAA 全量（2023 起）+ Single-A（FSL）；**AA 无公开数据**
  ——榜上 AA 新秀拿不到 Tier B，会自动落 Tier C 并在层级列如实标注
  （按人的精确级别可用 statsapi /people/{id}/stats?sportId=<11..14> 逐级查，
  留给二期 call-up 监控，本期不做每人多请求）
- MLB 聚合查询（含春训）：把域名路径换成 ``/statcast_search/csv``，
  加 ``game_type=S``（春训）与 ``minors=false``，按 player_id 逐人查询
- 聚合行可用列：pitches(面对投球数)/velocity/spin_rate/whiffs，
  打者为自身 woba/xwoba/launch_speed(平均击球初速)；投手为对手 woba/xwoba

设计要点：
- 整级批量（4 次请求覆盖 AAA/A × 打者/投手），远省于逐人查询
- 缓存复用 MLBStatsClient 的 JSON 机制，7 天 TTL（聚合榜周级新鲜度足够）
- 数值列统一转 float/int；请求失败返回 None，不中断雷达链路
- 本模块不拼装本地存储路径（复用既有缓存机制），URL 一律由白名单常量模板生成
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from ..config import get_season
from ..utils.logger import get_logger
from .mlb_api import _http_get_text, MLBStatsClient

logger = get_logger("data_fetch.milb_statcast")

_MINORS_CSV_BASE = "https://baseballsavant.mlb.com/statcast-search-minors/csv"
_MLB_CSV_BASE = "https://baseballsavant.mlb.com/statcast_search/csv"
_DEFAULT_TTL_HOURS = 7 * 24

# 公开 tracking 白名单提示（AA 无公开数据）；批查询本身返回全部 tracked 级别
TRACKED_LEVELS = ("AAA", "A")
_VALID_PLAYER_TYPES = ("batter", "pitcher")

# 聚合行需要转数值的列（其余列原样保留字符串）
_INT_COLUMNS = ("pitches", "total_pitches", "whiffs", "swings", "takes", "pa",
                "so", "bb", "hits", "hrs", "doubles", "triples", "singles",
                "barrels_total", "bip", "player_id")
_FLOAT_COLUMNS = ("velocity", "effective_speed", "spin_rate", "launch_speed",
                  "launch_angle", "ba", "iso", "babip", "slg", "woba", "xwoba",
                  "xba", "xslg", "obp", "k_percent", "bb_percent",
                  "swing_miss_percent", "hardhit_percent",
                  "barrels_per_bbe_percent", "barrels_per_pa_percent")


def _parse_aggregate_csv(text: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    """解析 Savant 聚合 CSV 为字典列表，数值列转类型。失败返回 None。

    表头清洗：批查询 CSV 首列带 UTF-8 BOM 且字段名带引号残留
    （实测为 '\\ufeff\"pitches\"'），逐列剥离后再用。
    """
    if not text or "player_name" not in text:
        logger.debug("MiLB Statcast 返回内容异常（无表头）")
        return None
    text = text.lstrip("\ufeff")
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for raw in reader:
            clean: Dict[str, Any] = {}
            for key, val in raw.items():
                if key is None or val is None or val == "":
                    continue
                key = str(key).strip().strip('"').strip()
                if key in _INT_COLUMNS:
                    try:
                        clean[key] = int(float(val))
                    except (TypeError, ValueError):
                        pass
                elif key in _FLOAT_COLUMNS:
                    try:
                        clean[key] = float(val)
                    except (TypeError, ValueError):
                        pass
                else:
                    clean[key] = val
            rows.append(clean)
    except csv.Error as e:
        logger.debug("MiLB Statcast CSV 解析失败: %s", e)
        return None
    return rows or None


class MilbStatcastFetcher:
    """MiLB Statcast 聚合快照抓取（Tier B）与 MLB 春训快照（Tier D）。

    缓存读写复用 MLBStatsClient 的 JSON 缓存（TTL/目录策略一致，
    本模块不自行拼装存储路径）。
    """

    def __init__(self, cache_dir: Optional[str] = None,
                 cache_ttl_hours: int = _DEFAULT_TTL_HOURS):
        self._store = MLBStatsClient(cache_dir=cache_dir,
                                     cache_ttl_hours=cache_ttl_hours)

    # -------------------------------------------------------------- Tier B
    def fetch_tracked_players(self, player_type: str,
                              season: Optional[int] = None,
                              force: bool = False) -> Optional[List[Dict[str, Any]]]:
        """全部有公开 tracking 的小联盟球员聚合快照（打者/投手二选一）。

        Args:
            player_type: batter / pitcher
        Returns:
            聚合行列表；参数非法、网络失败或无数据返回 None。
        """
        if player_type not in _VALID_PLAYER_TYPES:
            logger.debug("非法参数 player_type=%s", player_type)
            return None
        season = season or get_season()
        cache_key = f"milbsc_all_{player_type}_{season}"
        if not force:
            cached = self._store._load_cache(cache_key)
            if cached is not None:
                return cached
        url = (
            f"{_MINORS_CSV_BASE}?all=true&player_type={player_type}"
            f"&season={int(season)}&minors=true&wbc=false"
        )
        rows = _parse_aggregate_csv(_http_get_text(url, timeout=60))
        if rows is None:
            logger.warning("MiLB Statcast 抓取失败: %s %s", player_type, season)
            return None
        logger.info("MiLB Statcast tracked/%s/%s：%d 人聚合行", player_type, season, len(rows))
        self._store._save_cache(cache_key, rows)
        return rows

    def build_player_index(self, season: Optional[int] = None,
                           force: bool = False) -> Dict[int, Dict[str, Any]]:
        """合并打者/投手两批快照，输出 mlb_id → 聚合统计索引。

        级别归因不在本层（服务端忽略 level 过滤，见模块 docstring）；
        个别批次失败不影响整体（雷达对该批降级到 Tier C）。
        """
        season = season or get_season()
        index: Dict[int, Dict[str, Any]] = {}
        for player_type in _VALID_PLAYER_TYPES:
            rows = self.fetch_tracked_players(player_type, season, force=force)
            if not rows:
                continue
            for row in rows:
                pid = row.get("player_id")
                if not pid:
                    continue
                index[int(pid)] = {"player_type": player_type, "stats": row}
        return index

    # -------------------------------------------------------------- Tier D
    def fetch_spring_stats(self, player_id: int, player_type: str,
                           season: Optional[int] = None,
                           force: bool = False) -> Optional[Dict[str, Any]]:
        """MLB 春训聚合统计（game_type=S，逐人查询）。

        春训数据在选秀窗口（次年 2-3 月）才新鲜，由调用方显式启用；
        无跟踪记录 / 网络失败返回 None（层级自动回落）。
        """
        if player_type not in _VALID_PLAYER_TYPES:
            return None
        season = season or get_season()
        pid = int(player_id)
        cache_key = f"springsc_{pid}_{player_type}_{season}"
        if not force:
            cached = self._store._load_cache(cache_key)
            if cached is not None:
                return cached or None
        url = (
            f"{_MLB_CSV_BASE}?player_id={pid}&player_type={player_type}"
            f"&game_type=S&season={int(season)}&minors=false&wbc=false"
        )
        rows = _parse_aggregate_csv(_http_get_text(url, timeout=30))
        row = rows[0] if rows else None
        # 空结果也写缓存（None→[]），避免春训无记录的球员反复打网络
        self._store._save_cache(cache_key, row or [])
        return row
