"""FA（自由球员）分析模块。

迁移自旧版 ``fa_analyzer/``，所有数据库访问改走仓储层（``db_session``），
消除旧版每个方法内 connect_db/disconnect_db 的样板。价值计算、推荐算法
与旧版保持一致。
"""

from .analyzer import FAAnalyzer
from .real_time import RealTimeData
from .recommendation import RecommendationSystem

__all__ = ["FAAnalyzer", "RealTimeData", "RecommendationSystem"]
