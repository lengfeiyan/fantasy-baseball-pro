"""实时数据处理：球员统计、FA 池、伤病。

真实数据源：
- 球员赛季统计：MLB Stats API（``statsapi.mlb.com``）
- 伤病动态：MLB Stats API transactions
- Statcast：Baseball Savant

数据获取优先用真实源，失败时降级到内置 mock（保证离线可用）。
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import get_config, resolve_path
from ..data_fetch.mlb_api import MLBStatsClient
from ..data_fetch.statcast import StatcastFetcher
from ..db import FaRepository, InjuryRepository, db_session
from ..utils.logger import get_logger

logger = get_logger("fa.real_time")

# 当前赛季（用于查统计）
def _current_season() -> int:
    return datetime.now().year

# Mock FA 池数据（含 MLB player_id，便于查真实统计）
# player_id = MLB id，让 fetch_player_stats 能查真实数据
_MOCK_FA_POOL = [
    {"player_id": 545361, "name": "Mike Trout", "team": "LAA", "pos": "OF", "status": "available"},
    {"player_id": 592450, "name": "Aaron Judge", "team": "NYY", "pos": "OF", "status": "available"},
    {"player_id": 660271, "name": "Shohei Ohtani", "team": "LAD", "pos": "SP", "status": "available"},
    {"player_id": 605141, "name": "Mookie Betts", "team": "LAD", "pos": "OF", "status": "available"},
    {"player_id": 665742, "name": "Fernando Tatis Jr.", "team": "SD", "pos": "SS", "status": "available"},
]


def _mock_player_stats(player_id: int) -> Dict[str, Any]:
    """生成 mock 球员统计数据（真实数据不可用时的降级）。"""
    return {
        "player_id": player_id,
        "name": f"Player {player_id}",
        "team": "FA",
        "pos": "OF",
        "stats": {
            "AVG": 0.275, "HR": 15, "RBI": 50, "R": 60, "SB": 10,
            "OBP": 0.350, "SLG": 0.450, "OPS": 0.800, "WAR": 2.5,
        },
        "statcast": {
            "exit_velocity": 90.5, "launch_angle": 15.0, "xwOBA": 0.340,
            "hard_hit_rate": 0.35, "barrel_rate": 0.10,
            "swing_contact_rate": 0.80,
        },
        "last_updated": datetime.now().isoformat(),
    }


class RealTimeData:
    """实时数据处理（真实数据 + mock 降级）。"""

    def __init__(self, conn=None, cache_dir: Optional[str] = None, season: Optional[int] = None):
        self._conn = conn
        cfg = get_config().get("fa_analyzer", {}).get("cache", {})
        self.cache_dir = resolve_path(cache_dir or cfg.get("directory", "data/cache"))
        self.cache_expiry = cfg.get("expiry", 24) * 3600
        self.season = season or _current_season()
        os.makedirs(self.cache_dir, exist_ok=True)
        # 真实数据客户端
        self._mlb = MLBStatsClient(cache_dir=self.cache_dir)
        self._statcast = StatcastFetcher(cache_dir=self.cache_dir)

    # -------------------------------------------------------------- 球员统计
    def fetch_player_stats(self, player_id: int) -> Dict[str, Any]:
        """获取球员统计（真实优先，降级 mock）。

        player_id 在真实模式下是 MLB player_id。
        """
        # 1. 本地缓存
        cached = self._load_cache(f"player_{player_id}")
        if cached:
            return cached

        # 2. MLB Stats API 真实数据
        try:
            stats = self._mlb.fetch_player_stats(player_id, self.season)
            if stats:
                # 补充 Statcast
                statcast = self._fetch_statcast_safely(player_id, stats.get("pos", ""))
                if statcast:
                    stats["statcast"] = statcast
                self._save_cache(f"player_{player_id}", stats)
                return stats
        except Exception as e:
            logger.warning("MLB 统计获取失败 (id=%d)，降级 mock: %s", player_id, e)

        # 3. mock 降级
        logger.info("使用 mock 统计数据 (player_id=%d)", player_id)
        mock = _mock_player_stats(player_id)
        return mock

    def _fetch_statcast_safely(self, player_id: int, pos: str) -> Dict[str, Any]:
        """安全获取 Statcast（失败返回空 dict 不中断）。"""
        try:
            # 投手类位置（含两刀流 TWP）走投手 Statcast
            if pos in ("P", "TWP", "SP", "RP"):
                return self._statcast.fetch_pitcher_data(player_id, self.season)
            # 其余（含 CF/RF/LF/SS 等打者位置）走打者 Statcast
            return self._statcast.fetch_hitter_data(player_id, self.season)
        except Exception as e:
            logger.warning("Statcast 获取失败 (id=%d): %s", player_id, e)
            return {}

    # -------------------------------------------------------------- FA 池
    def update_fa_pool(self) -> List[Dict[str, Any]]:
        """更新 FA 池（mock 数据写入数据库）。

        FA 池本身无单一公开数据源（取决于用户联盟），保留 mock。
        但 player_id 现在是 MLB id，可查真实统计。
        """
        def _do(conn):
            repo = FaRepository(conn)
            for player in _MOCK_FA_POOL:
                existing = repo.find_in_pool(player["name"])
                if existing:
                    conn.execute(
                        "UPDATE fa_pool SET team=?, pos=?, status=?, last_updated=CURRENT_TIMESTAMP WHERE name=?",
                        (player["team"], player["pos"], player["status"], player["name"]),
                    )
                else:
                    repo.add_to_pool(player)
            return _MOCK_FA_POOL
        result = self._run(_do)
        logger.info("FA 池更新完成：%d 名球员（含真实 MLB id）", len(result))
        return result

    # -------------------------------------------------------------- 伤病
    def update_injury_data(
        self, days_back: int = 30, allow_network: bool = True
    ) -> List[Dict[str, Any]]:
        """更新伤病数据（真实 MLB transactions）。

        Args:
            days_back: 回溯天数（默认 30 天）。
            allow_network: 是否允许联网。False 时跳过抓取（测试用）。
        """
        if not allow_network:
            logger.info("跳过伤病抓取（allow_network=False）")
            return []

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # 修复 M3：网络失败要抛异常（让 GUI 显示错误），0 条则正常返回空列表
        try:
            injuries = self._mlb.fetch_injuries(start_date, end_date)
        except Exception as e:
            logger.error("伤病抓取失败: %s", e)
            raise RuntimeError(f"伤病数据抓取失败（网络不可用？）: {e}") from e

        if not injuries:
            logger.info("未抓取到伤病数据（该时段可能无伤病动态）")
            return []

        def _do(conn):
            repo = InjuryRepository(conn)
            repo.replace_all(injuries)
            return injuries
        result = self._run(_do)
        logger.info("伤病数据更新完成：%d 条（最近 %d 天）", len(result), days_back)
        return result

    # -------------------------------------------------------------- 文件导入
    def import_data_from_file(self, file_path: str, data_type: str) -> int:
        """从 CSV 导入数据到对应表。"""
        path = resolve_path(file_path)
        if not os.path.exists(path):
            logger.error("文件不存在: %s", path)
            return 0
        df = pd.read_csv(path)

        def _do(conn):
            if data_type == "fa_pool":
                rows = df.to_dict("records")
                FaRepository(conn).replace_pool(rows)
                return len(rows)
            elif data_type == "injury":
                rows = df.to_dict("records")
                InjuryRepository(conn).replace_all(rows)
                return len(rows)
            logger.warning("未知数据类型: %s", data_type)
            return 0
        return self._run(_do)

    # -------------------------------------------------------------- 缓存
    def _cache_file(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def _load_cache(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._cache_file(key)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.cache_expiry:
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
            logger.warning("写入缓存失败: %s", e)

    # -------------------------------------------------------------- 工具
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
