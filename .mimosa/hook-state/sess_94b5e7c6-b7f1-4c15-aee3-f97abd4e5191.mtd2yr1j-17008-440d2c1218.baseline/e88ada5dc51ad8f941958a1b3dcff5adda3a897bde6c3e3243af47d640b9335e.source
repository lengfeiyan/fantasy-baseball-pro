"""伤病数据抓取。

迁移自旧版 ``data/injury_data.py``。从 MLB Stats API 抓取伤病报告。
``requests`` 为可选依赖。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger("data_fetch.injury")

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class InjuryDataFetcher:
    """伤病数据抓取器。"""

    def fetch_injury_data(self) -> List[Dict[str, Any]]:
        """抓取当前伤病列表。"""
        if not _HAS_REQUESTS:
            raise ImportError("抓取伤病数据需要 requests 库：pip install requests")
        logger.warning("伤病数据真实抓取未实现，返回 mock 数据")
        return self._mock_injuries()

    @staticmethod
    def _mock_injuries() -> List[Dict[str, Any]]:
        return [
            {"player_id": 1, "name": "Mike Trout", "injury_type": "背部", "severity": "mild"},
            {"player_id": 3, "name": "Shohei Ohtani", "injury_type": "手肘", "severity": "moderate"},
        ]
