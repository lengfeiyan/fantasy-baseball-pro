动态选秀模拟器（Dynamic Draft Simulator）
不再猜测“谁能活到我选”——用 10,000 次智能模拟，精准锁定你的 Sleeper！
基于真实人类经理策略（囤位置、信 Statcast、跟 ADP），而非机械排序，为你在第 X 顺位提供高概率可捡球员清单。
✨ 核心优势
表格
传统工具	本模拟器
❌ 假设所有对手按 ADP 选人	✅ 4 类 AI 经理人：均衡型、位置囤积型、Statcast 信徒、ADP 跟随者
❌ 静态结果（“他是 Sleeper”）	✅ 概率化输出（“82% 概率活到你第 6 轮”）
❌ 忽略你的个人策略	✅ 内置你的专属策略：前期抢 SP → 中期囤新秀 → 后期捡 Statcast 红利
❌ 模拟 100 次需数分钟	✅ 10,000 次模拟 <10 秒（Numba 加速 + 向量化）
📦 项目结构
text

编辑



fantasy-baseball-pro/
├── draft_simulator/              # 动态选秀模拟器核心
│   ├── __init__.py
│   ├── ai_strategies.py          # AI 经理人策略（含你的个人策略）
│   ├── draft_engine.py           # 高性能模拟引擎（支持 10k+ 次模拟）
│   └── run_simulation.py         # 主入口脚本
├── data/
│   ├── rankings_with_vorp.csv    ← 来自 fantasy_scoring_model_v2.py
│   ├── adp.csv                   ← 来自 fetch_adp_cached.py
│   ├── statcast_batter_2025.csv  ← （可选但强烈推荐）
│   └── statcast_pitcher_2025.csv ← （可选但强烈推荐）
├── config.yaml                   # 联盟配置（队伍数、轮次等）
└── reports/
    ├── draft_simulation_full_results.csv
    └── draft_simulation_top_sleepers.csv
⚙️ 快速开始
1. 安装依赖
bash

编辑



pip install pandas numpy pyyaml numba
2. 准备数据
确保已生成以下文件：
bash

编辑



python fantasy_scoring_model_v2.py   # → data/rankings_with_vorp.csv
python fetch_adp_cached.py           # → data/adp.csv
💡 强烈建议：手动下载 Baseball Savant 的 2025 赛季数据并保存为：
data/statcast_batter_2025.csv
data/statcast_pitcher_2025.csv
3. 配置联盟规则（config.yaml 示例）
yaml

编辑



league:
  size: 12        # 联盟队伍数
  rounds: 15      # 选秀轮次
  roster_slots:
    C: 1
    1B: 1
    2B: 1
    3B: 1
    SS: 1
    OF: 5
    UTIL: 1
    SP: 6
    RP: 2
4. 运行模拟
bash

编辑



# 基础命令：你的顺位是第 8，运行 10,000 次模拟
python -m draft_simulator.run_simulation --user-pick 8

# 自定义参数
python -m draft_simulator.run_simulation \
  --user-pick 5 \
  --simulations 5000 \
  --min-availability 0.25
📊 输出解读
终端输出示例
text

编辑



🎯 Top 10 高概率 Sleeper (可用率 ≥ 30%):
================================================================================
球员                     | 可用率   | 平均轮次   | VORP     | ADP
--------------------------------------------------------------------------------
Jackson Holliday         | 89%     | 5.1       | 118.2    | 120
Grayson Rodriguez        | 82%     | 6.3       | 94.5     | 140
Adley Rutschman          | 76%     | 4.8       | 92.3     | 100
...
生成文件
表格
文件	说明
reports/draft_simulation_top_sleepers.csv	重点关注：可用率 ≥ 阈值的高价值目标
reports/draft_simulation_full_results.csv	完整数据：所有球员的模拟统计（用于深度分析）
🧠 你的个人策略详解
本模拟器内置 YourStrategyDrafter，完美复刻你的选秀哲学：
表格
选秀阶段	策略	目标
前 3 轮	只考虑先发投手（SP）	抢占稀缺精英投手（Skenes, Rogers 等）
4–8 轮	锁定 ≤25 岁高 VORP 打者	捕捉新秀/二年级飞跃红利（Holliday, Melendez）
9+ 轮	专注 Statcast 信号	捡漏 xwOBA≥.34 或 xERA≤3.5 的“运气差”球员
✅ 该策略已融入模拟逻辑——系统知道你在前 3 轮不会碰打者，因此会更准确预测打者池的消耗速度。
🔧 高级用法
调整可用率阈值
bash

编辑



# 查看更多潜在目标（降低至 20%）
python -m draft_simulator.run_simulation --min-availability 0.2
快速测试（低模拟次数）
bash

编辑



# 1,000 次模拟（约 1 秒）
python -m draft_simulator.run_simulation --simulations 1000
多顺位对比
bash

编辑



# 测试顺位 5 vs 8 的差异
python -m draft_simulator.run_simulation --user-pick 5 --simulations 5000
python -m draft_simulator.run_simulation --user-pick 8 --simulations 5000
⚡ 性能说明
表格
模拟次数	预期耗时	硬件要求
1,000	～1 秒	任何现代电脑
5,000	～5 秒	推荐 8GB+ 内存
10,000	～10 秒	最佳实践（统计显著）
💡 首次运行会 JIT 编译 numba 函数（稍慢），后续运行极速。
❓ 常见问题
Q：没有 Statcast 数据能运行吗？
A：可以！但推荐度会降低。脚本会自动跳过 Statcast 相关逻辑。
Q：如何修改我的个人策略？
A：编辑 draft_simulator/ai_strategies.py 中的 YourStrategyDrafter 类。
Q：支持 Keeper/Dynasty 联盟吗？
A：当前为红人联盟（Redraft）设计。Keeper 联盟需额外注入保留球员逻辑（可扩展）。
🚀 下一步
将结果导入 选秀夜实时助手 GUI
添加 “反事实分析”：如果我跳过 A，B 会活下来吗？
集成 每日更新的伤病/角色变动
⚾ 现在，带着数据洞察走进选秀室——让每一次选择都建立在 10,000 次未来之上。