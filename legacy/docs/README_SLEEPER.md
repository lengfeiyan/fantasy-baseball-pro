✅ find_sleeper_players.py（基础版）
✅ find_sleeper_players_statcast_v2.0.py（Statcast 增强版）
🕵️‍♂️ Fantasy Baseball Sleeper 推荐器
自动发现被市场低估的高潜力球员 —— 从基础价值偏差到 Statcast 深度信号，助你在选秀后期或赛季中抢占先机。

📦 脚本概览
| 脚本 | 版本 | 功能 | 依赖数据 |
|------|------|------|----------|
| `find_sleeper_players.py` | v1.0 | 基于 VORP vs ADP 偏差 识别 Sleeper | 预测数据 + ADP |
| `find_sleeper_players_statcast_v2.0.py` | v2.0 | 融合 Statcast 底层指标（xwOBA, xERA 等），挖掘“运气差”红利球员 | 预测数据 + ADP + 手动下载的 Statcast CSV |

💡 推荐使用顺序：先用 v1.0 快速扫描，再用 v2.0 深度验证关键目标。

🚀 快速开始

1. **准备基础数据**（两个脚本都需要）
   确保已生成以下文件（通过主项目流程）：
   ```bash
   python fantasy_scoring_model_v2.py   # → fantasy_draft_rankings_vorp_2026.csv
   python fetch_adp_cached.py           # → adp.csv
   ```

2. **（仅 v2.0 需要）下载 Statcast 数据**
   - 访问 [Baseball Savant](https://baseballsavant.mlb.com/)
   - 分别导出 打者 和 投手 的完整赛季数据（建议使用 2025 或最新完整赛季）
   - 保存至 `data/` 目录，命名如下：
     - `data/statcast_batter_2025.csv`
     - `data/statcast_pitcher_2025.csv`
   ⚠️ 脚本会自动将 Savant 的 "Last, First" 姓名格式转换为 "First Last" 以匹配预测数据。

3. **运行脚本**

   **基础版（v1.0）**
   ```bash
   # 全位置 Top 20 Sleeper
   python find_sleeper_players.py --top 20

   # 专注捕手（ADP 100～200）
   python find_sleeper_players.py --position C --min-adp 100 --max-adp 200
   ```

   **Statcast 增强版（v2.0）**
   ```bash
   # 全位置 Top 15 Statcast Sleeper
   python find_sleeper_players_statcast_v2.0.py --top 15

   # 专注投手（ADP 120+）
   python find_sleeper_players_statcast_v2.0.py --position SP --min-adp 120
   ```

📊 输出说明

两个脚本均会：
- 在终端打印 高亮推荐列表
- 生成 CSV 报告至 `reports/` 目录

**示例输出（v2.0）**
```text
🔥 Top 13 Statcast Sleeper v2.0 (ADP 1-30)
========================================================================================================
Gerrit Cole          (SP) | ADP: 22.3 → 应有:   10 | VORP:   5.8 | 被低估 12.3 顺位
José Ramírez         (3B) | ADP: 19.4 → 应有:    8 | VORP:  10.0 | 被低估 11.4 顺位
Kyle Tucker          (OF) | ADP: 17.3 → 应有:    6 | VORP:  15.0 | 被低估 11.3 顺位
```

**生成文件**
- `reports/sleeper_recommendations.csv`（v1.0）
- `reports/sleeper_statcast_v2.0.csv`（v2.0）

🔍 核心逻辑

**v1.0：价值偏差模型**
- 预期顺位 = VORP 排名
- Sleeper 条件：ADP - 预期顺位 ≥ 阈值（默认 30）
- 适合快速识别 传统估值错误

**v2.0：Statcast 信号增强**
在 v1.0 基础上，额外筛选具有以下特征的球员：

**打者**
- xwOBA ≥ 0.340 但 AVG < 0.250 → 运气差，即将反弹
- exit_velocity ≥ 90 mph 且 barrel% ≥ 8% → 硬核击球能力

**投手**
- xERA ≤ 3.5 但 ERA > 4.5 → 防御运气差
- whiff% ≥ 30% 且 K% ≥ 25% → 真实压制力被低估

✅ 这些是职业分析师判断“可持续表现”的黄金指标。

⚙️ 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --min-adp | 80 | 最小 ADP（避免推荐太早被选的球员） |
| --max-adp | 300 | 最大 ADP（聚焦后期可选范围） |
| --min-bias | 30 | 最小低估顺位（v1.0）或 Statcast 信号强度（v2.0） |
| --position | — | 仅分析特定位置（如 C, SS, SP） |
| --top | 20 (v1.0) / 15 (v2.0) | 输出前 N 名 |

💡 使用场景

| 场景 | 推荐脚本 |
|------|----------|
| 选秀前一周：快速扫描后期宝藏 | v1.0 |
| 深度联盟（15+队）：挖掘冷门价值 | v1.0 + v2.0 |
| 赛季中交易：识别对手忽略的 Statcast 红利股 | v2.0 |
| 每日监控：结合最新伤病动态调整目标 | v2.0 |

📁 项目结构

```text
fantasy-baseball-pro/
├── find_sleeper_players.py                 # v1.0 基础版
├── find_sleeper_players_statcast_v2.0.py   # v2.0 Statcast 增强版
├── fantasy_draft_rankings_vorp_2026.csv    # ← fantasy_scoring_model_v2.py 生成
├── adp.csv                                 # ← fetch_adp_cached.py 生成
├── data/
│   ├── statcast_batter_2025.csv            # ← 手动下载（v2.0 需要）
│   └── statcast_pitcher_2025.csv           # ← 手动下载（v2.0 需要）
└── reports/
    ├── sleeper_recommendations.csv         # v1.0 输出
    └── sleeper_statcast_v2.0.csv           # v2.0 输出
```

� 注意事项

- 两个脚本均为 独立运行，不依赖 GUI。
- 若 Statcast 文件缺失，v2.0 脚本会跳过对应分析，返回基础筛选结果。
- 姓名匹配基于 "First Last" 格式，请确保预测数据与 Statcast 转换后一致。
- ADP 数据建议使用最近 7 天内更新，避免过时偏差。
- 脚本会自动处理列名冲突，确保合并数据时使用正确的字段。