"""首页 + 帮助选项卡（合并）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import __version__
from ...config import current_season
from ._widgets import set_text, text_display


HELP_TEXT = f"""\
快速开始
==========================================
1. 数据管理 → 「网络获取预测」从 FantasyPros 抓取 800+ 球员预测
2. 配置设置 → 调整联盟规则（评分权重/阵容槽位）
3. 分析流水线 → 生成 VORP 排名 + 准备 ADP
4. 选秀中心 → 单次模拟看阵容 / 蒙特卡洛看可用概率
5. 阵容验证 → 导入阵容（FA推荐会基于此分析位置需求）
6. Sleeper挖掘 → 发现被低估的球员
7. FA分析 → 赛季中自由球员推荐（真实数据）

命令行使用
==========================================
  python -m fantasy_baseball fetch-projections --season {current_season()}
  python -m fantasy_baseball rank
  python -m fantasy_baseball adp
  python -m fantasy_baseball draft --pick 5
  python -m fantasy_baseball sleeper
  python -m fantasy_baseball roster import output/draft_log_pick5_balanced.csv
  python -m fantasy_baseball mlb "Aaron Judge" --statcast
  python -m fantasy_baseball fa recommend

所有生成的排名/选秀日志/FA 导出统一存放在 output/ 目录。

真实数据源（全部免费、无需 key）
==========================================
  - 预测数据：FantasyPros（聚合 Steamer/ZiPS/THE BAT X/ATC）
  - ADP：FantasyPros（聚合 Yahoo/CBS/NFBC/ESPN，597名球员）
  - 球员统计：MLB Stats API（AVG/HR/ERA 等）
  - Statcast：Baseball Savant（exit velocity/xwOBA 等）
  - 伤病：MLB Stats API transactions
所有数据源失败时降级到 mock，保证离线可用。

常见问题
==========================================
Q: 启动报错找不到模块？
A: 确保安装 pip install -e . 或设置 PYTHONPATH=src

Q: 数据库如何重建？
A: 删除 fantasy_baseball.db，程序会自动重建空表

Fantasy Baseball Pro v{__version__}
"""


def create_tab(parent: tk.Widget, app) -> None:
    # 标题
    header = ttk.Frame(parent)
    header.pack(fill=tk.X, pady=(8, 4))
    ttk.Label(header, text="Fantasy Baseball Pro", font=("", 16, "bold")).pack()
    ttk.Label(header, text=f"v{__version__} | 专业级分析与选秀模拟系统").pack()

    # 帮助文本
    _, text = text_display(parent, height=28)
    set_text(text, HELP_TEXT)

    # 完整文档提示
    ttk.Label(
        parent,
        text="完整帮助文档见项目根目录的 USER_GUIDE.md",
        font=("", 9),
    ).pack(anchor=tk.W, pady=(4, 0))
