"""帮助选项卡。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import __version__
from ._widgets import set_text, text_display


HELP_TEXT = f"""\
Fantasy Baseball Pro v{__version__}
==========================================

【快速开始】
1. 数据管理 → 选择 CSV 文件 → 导入数据
2. 配置设置 → 调整联盟规则 → 保存配置
3. 分析流水线 → 运行完整流水线（导入 + 排名 + ADP）
4. 选秀模拟 → 设置顺位与策略 → 模拟选秀
5. 阵容验证 → 选择选秀日志 → 验证合规性

【命令行使用】
  python -m fantasy_baseball ingest     # 导入数据
  python -m fantasy_baseball rank       # 生成排名
  python -m fantasy_baseball draft --pick 5
  python -m fantasy_baseball simulate --user-pick 5 --iterations 5000
  python -m fantasy_baseball sleeper
  python -m fantasy_baseball validate draft_log_pick5_balanced.csv
  python -m fantasy_baseball mlb "Aaron Judge" --statcast  # 查真实数据
  python -m fantasy_baseball fa update-injury --days-back 60

【数据准备】
从 FanGraphs 下载预测 CSV 到 data/ 目录：
  - hitters_2026_steamer.csv（打者）
  - pitchers_2026_steamer.csv（投手）
  - player_positions_2025.csv（位置映射，必需）

【真实数据源】（全部免费、无需 key）
  - ADP：FantasyPros（约 600 名球员，聚合多平台）
  - 球员统计：MLB Stats API（AVG/HR/ERA 等）
  - Statcast：Baseball Savant（exit velocity/xwOBA 等）
  - 伤病：MLB Stats API transactions（含严重度分级）
所有数据源失败时降级到 mock，保证离线可用。

【项目结构】
  src/fantasy_baseball/   主包
  config.yaml             配置文件（核心）
  data/                   输入 CSV
  legacy/                 旧版脚本（已归档，仅供参考）

【常见问题】
Q: 启动报错找不到模块？
A: 确保安装：pip install -e . 或设置 PYTHONPATH=src

Q: 数据库如何重建？
A: 删除 fantasy_baseball.db，程序会自动重建空表

Q: ADP 数据是真实的吗？
A: 是。从 FantasyPros 抓取真实 ADP。强制刷新：python -m fantasy_baseball adp --force
"""


def create_tab(parent: tk.Widget, app) -> None:
    _, text = text_display(parent, height=30)
    set_text(text, HELP_TEXT)
