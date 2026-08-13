"""数据抓取模块：MLB Stats API、Statcast、伤病数据、预测数据。

四个真实数据源（全部免费、无需 API key）：
- MLB Stats API（statsapi.mlb.com）：球员赛季统计、伤病动态
- Baseball Savant：Statcast 高级数据（逐投球聚合）
- FantasyPros：ADP + 预测数据（聚合 Steamer/ZiPS/THE BAT X/ATC）
依赖：标准库 urllib + 已有的 pandas
"""

from .mlb_api import MLBStatsClient
from .projections import fetch_projections
from .statcast import StatcastFetcher

__all__ = ["MLBStatsClient", "StatcastFetcher", "fetch_projections"]
