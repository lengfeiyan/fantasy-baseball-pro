# Fantasy Baseball Pro 用户帮助文档

> **版本**：2026.1.0
> **更新日期**：2026-08-11
> **适用对象**：从零基础新手到资深 Fantasy Baseball 玩家

---

## 目录

1. [项目简介](#1-项目简介)
2. [安装与配置](#2-安装与配置)
3. [快速开始（5分钟上手）](#3-快速开始5分钟上手)
4. [GUI 图形界面详解](#4-gui-图形界面详解)
5. [命令行（CLI）完整参考](#5-命令行cli完整参考)
6. [数据源说明](#6-数据源说明)
7. [核心算法与评分逻辑](#7-核心算法与评分逻辑)
8. [配置文件（config.yaml）详解](#8-配置文件configyaml详解)
9. [常见使用场景](#9-常见使用场景)
10. [常见问题（FAQ）](#10-常见问题faq)
11. [离线使用与故障排除](#11-离线使用与故障排除)
12. [项目架构（开发者参考）](#12-项目架构开发者参考)

---

## 1. 项目简介

Fantasy Baseball Pro 是一套为严肃 Fantasy Baseball 玩家打造的**专业级分析与选秀模拟系统**。

### 核心能力

| 能力 | 说明 |
|------|------|
| **预测数据获取** | 自动从 FantasyPros 抓取 800+ 打者 + 900+ 投手的赛季预测（聚合 Steamer/ZiPS/THE BAT X/ATC） |
| **VORP 排名** | 根据你的联盟评分规则计算"替代球员之上的价值"，含风险上下限 |
| **选秀模拟** | 单次蛇形选秀（看阵容）+ 蒙特卡洛 10000 次模拟（看可用概率） |
| **Sleeper 挖掘** | 找出被市场低估的球员（VORP vs ADP 偏差 + Statcast 信号增强） |
| **FA 分析** | 赛季中自由球员推荐（真实统计 + Statcast + 伤病 + 趋势 + 位置需求） |
| **阵容验证** | 检查阵容合规性、分析强度、FA 推荐基于真实阵容缺口 |

### 设计特点

- **数据真实**：五个数据源全部免费、无需 API key
- **离线可用**：所有数据源失败时优雅降级到内置 mock 数据
- **零外部依赖**：核心仅需 pandas + numpy + pyyaml，其余可选

---

## 2. 安装与配置

### 环境要求

- Python 3.7 或更高
- 操作系统：Windows / macOS / Linux

### 安装方式

**方式 A：可编辑安装（推荐）**

```bash
cd fbtool
pip install -e .
```

安装后可直接使用 `fantasy-baseball` 命令，也能在任何目录 `import fantasy_baseball`。

**方式 B：仅设置路径（无需安装）**

```bash
# Linux/macOS
export PYTHONPATH=src

# Windows (Git Bash)
set PYTHONPATH=src

# Windows (PowerShell)
$env:PYTHONPATH="src"
```

### 依赖清单

**核心依赖**（必需）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| pandas | >=1.3, <3.0 | 数据处理 |
| numpy | >=1.20, <3.0 | 数值计算 |
| PyYAML | >=5.4, <7.0 | 配置文件解析 |

**可选依赖**：

| 依赖 | 版本 | 用途 |
|------|------|------|
| numba | >=0.55, <0.62 | 蒙特卡洛加速（未安装自动降级为纯 Python） |
| requests | >=2.25, <3.0 | 数据抓取（未安装时用标准库 urllib 降级） |

安装可选依赖：

```bash
pip install numba requests
```

---

## 3. 快速开始（5分钟上手）

### 一步到位流程

```bash
# 1. 抓取真实预测数据（首次需联网，约10秒）
python -m fantasy_baseball fetch-projections --season 2026

# 2. 生成 VORP 排名
python -m fantasy_baseball rank

# 3. 准备 ADP 数据（首次需联网）
python -m fantasy_baseball adp

# 4. 模拟选秀（你是第5顺位）
python -m fantasy_baseball draft --pick 5

# 5. 挖掘被低估的球员
python -m fantasy_baseball sleeper --min-adp 100 --max-adp 400

# 6. 查询某球员的真实数据
python -m fantasy_baseball mlb "Aaron Judge" --statcast
```

或者直接启动 GUI：

```bash
python -m fantasy_baseball gui
```

---

## 4. GUI 图形界面详解

启动 GUI：

```bash
python -m fantasy_baseball gui
```

界面包含 **10 个选项卡**，以下逐个说明。

### 4.1 首页

显示项目简介、快速开始指南、命令行示例、数据源说明和常见问题。

### 4.2 数据管理

管理预测数据的导入。

| 按钮 | 功能 |
|------|------|
| **网络获取预测** | 从 FantasyPros 抓取真实预测（800+ 打者 + 900+ 投手，推荐） |
| **CSV导入** | 从本地 CSV 导入（离线备选，需手动准备文件） |
| **查看状态** | 显示数据库各表行数 |

**网络获取**会同时自动填充位置映射（无需手动准备 `player_positions` 文件）。

### 4.3 配置设置

编辑联盟规则，所有改动保存到 `config.yaml`。

| 参数 | 说明 |
|------|------|
| 联盟规模 | 参赛队伍数（默认 12） |
| 选秀轮数 | 总轮次（默认 15） |
| 打者评分权重 | R/HR/RBI/SB/AVG 等各项的权重（正=加分） |
| 投手评分权重 | W/SV/HOLD/ERA/WHIP/K_per_9（ERA/WHIP 设为负值） |
| 默认策略 | conservative / balanced / aggressive |

保存时**保留原有注释**（逐行更新，不会丢失你写的中文说明）。

### 4.4 分析流水线

一键运行完整的分析流程。

| 按钮 | 功能 |
|------|------|
| **导入数据** | 等同数据管理的 CSV 导入 |
| **生成排名** | 计算 VORP 排名，输出到 `fantasy_draft_rankings_vorp_2026.csv` |
| **准备ADP** | 抓取/刷新 ADP 数据 |
| **运行完整流水线** | 上述三步一键执行 |

### 4.5 选秀中心

合并了单次选秀和蒙特卡洛模拟。

**单次蛇形选秀**：
- 设置顺位（1-联盟规模）和策略
- 点击「单次选秀」生成你的完整阵容
- 输出含每轮选择、VORP 值、价值股标记

**蒙特卡洛模拟**：
- 设置你的顺位和最小可用率阈值
- 点击「蒙特卡洛」估算各球员在你顺位被选中的概率
- 用途：判断"某球员能不能活到我选"

### 4.6 阵容验证

两个功能区：

**阵容验证**（从 CSV）：
- 选择选秀日志 CSV 文件
- 检查阵容合规性（各位置人数是否达标/超编）
- 分析阵容强度（总 VORP、打者/投手比例、各轮质量）

**我的阵容**（保存到数据库）：
- **从选秀日志导入**：把 CSV 的阵容写入数据库
- **查看阵容**：显示当前阵容 + 位置填充状态（C: 1/1 ✓, SP: 3/4 ⚠️）
- **清空阵容**

导入后，**FA 分析的推荐会优先填补你缺少的位置**。

### 4.7 Sleeper 挖掘

发现被市场低估的球员。

| 参数 | 说明 | 默认 |
|------|------|------|
| 最小ADP | 只看 ADP >= 此值的球员 | 80 |
| 最大ADP | 只看 ADP <= 此值的球员 | 300 |
| 最小低估 | ADP - 预期顺位 >= 此值才算低估 | 30 |
| 位置筛选 | 只看特定位置 | All |
| 启用Statcast | 融合 Statcast 信号（xwOBA/EV/barrel%） | 开 |

输出含偏差值和 Statcast 信号描述。

### 4.8 FA 分析

赛季中自由球员推荐。

| 按钮 | 功能 |
|------|------|
| **更新FA池(内置)** | 用内置示例数据填充 FA 池 |
| **导入FA池CSV** | 从 CSV 导入你联盟的真实 FA 池 |
| **查看FA池** | 显示当前 FA 池 |
| **更新伤病** | 从 MLB API 拉取真实伤病数据 |
| **生成推荐** | 基于 FA 价值 + 阵容需求 + 风险偏好排序 |
| **导出结果** | 推荐结果导出为 CSV |

**FA 池 CSV 格式**：

```csv
player_id,name,team,pos,status
1,Mike Trout,LAA,OF,available
```

（`player_id` 可留空，`name` 和 `pos` 必需）

### 4.9 数据探索

合并了 Statcast 查询和伤病列表。

**球员数据查询**：
- 输入球员姓名（如 "Aaron Judge"）和赛季
- 点击「查询球员」获取真实赛季统计 + Statcast 聚合数据

**伤病报告**：
- 点击「查看伤病」显示数据库中的伤病列表

### 4.10 插件管理

加载和管理插件。插件放在项目根的 `plugins/` 目录（每个插件一个子目录，含 `__init__.py`）。

---

## 5. 命令行（CLI）完整参考

启动方式：

```bash
python -m fantasy_baseball <命令> [参数]
```

无参数时默认启动 GUI。

### 5.1 数据导入

```bash
# 从网络抓取预测（推荐）
python -m fantasy_baseball fetch-projections --season 2026

# 从本地 CSV 导入（离线备选）
python -m fantasy_baseball ingest
```

### 5.2 排名与 ADP

```bash
# 生成 VORP 排名
python -m fantasy_baseball rank

# 准备/刷新 ADP 数据
python -m fantasy_baseball adp
python -m fantasy_baseball adp --force    # 强制刷新缓存
```

### 5.3 选秀模拟

```bash
# 单次蛇形选秀
python -m fantasy_baseball draft --pick 5 --strategy balanced

# 蒙特卡洛模拟（估算可用概率）
python -m fantasy_baseball simulate --user-pick 5 --min-availability 0.25
```

**策略说明**：

| 策略 | 行为 |
|------|------|
| `balanced` | 按标准 VORP 选人 |
| `conservative` | 优先选 vorp_floor 高的（稳定老将） |
| `aggressive` | 优先选 vorp_upside 高的（高风险高回报） |

### 5.4 Sleeper 挖掘

```bash
python -m fantasy_baseball sleeper \
    --min-adp 100 \
    --max-adp 400 \
    --min-bias 30 \
    --top 15 \
    --position OF \
    --no-statcast
```

### 5.5 阵容管理

```bash
# 从选秀日志导入阵容
python -m fantasy_baseball roster import draft_log_pick5_balanced.csv

# 查看当前阵容 + 位置填充状态
python -m fantasy_baseball roster show

# 清空阵容
python -m fantasy_baseball roster clear

# 手动添加/删除球员
python -m fantasy_baseball roster add "Mike Trout" --pos OF --team LAA
python -m fantasy_baseball roster remove "Mike Trout"
```

### 5.6 阵容验证

```bash
# 基础验证
python -m fantasy_baseball validate draft_log_pick5_balanced.csv

# 含强度分析
python -m fantasy_baseball validate draft_log_pick5_balanced.csv --analyze
```

### 5.7 FA 分析

```bash
# 更新 FA 池（内置示例数据）
python -m fantasy_baseball fa update-fa

# 更新伤病（真实 MLB 数据）
python -m fantasy_baseball fa update-injury --days-back 60

# 从 CSV 导入你联盟的 FA 池
python -m fantasy_baseball fa import-pool --file my_fa_pool.csv

# 查看 FA 池
python -m fantasy_baseball fa show-pool

# 生成推荐
python -m fantasy_baseball fa recommend --position SP --risk balanced --top 10
```

### 5.8 MLB 球员查询

```bash
# 查询赛季统计
python -m fantasy_baseball mlb "Aaron Judge" --season 2025

# 含 Statcast
python -m fantasy_baseball mlb "Aaron Judge" --season 2025 --statcast
```

### 5.9 GUI

```bash
python -m fantasy_baseball gui
```

---

## 6. 数据源说明

全部数据源**免费、无需 API key**。

| 数据 | 来源 | 更新频率 | 离线降级 |
|------|------|----------|----------|
| **预测数据** | [FantasyPros](https://www.fantasypros.com/mlb/projections/) | 手动触发 | 无（需联网或本地 CSV） |
| **ADP** | [FantasyPros](https://www.fantasypros.com/mlb/adp/overall.php) | 12 小时缓存 | 25 条内置 mock |
| **球员赛季统计** | [MLB Stats API](https://statsapi.mlb.com) | 6 小时缓存 | mock 兜底 |
| **Statcast** | [Baseball Savant](https://baseballsavant.mlb.com) | 24 小时缓存 | mock 兜底 |
| **伤病动态** | [MLB Stats API](https://statsapi.mlb.com) transactions | 6 小时缓存 | 无 |
| **趋势分** | MLB Stats API `gameLog` | 6 小时缓存 | 返回中性值 100 |

### 关于预测数据

FanGraphs 自 2026 年起全面封禁非浏览器请求（403），本项目改用 **FantasyPros** 作为预测源——它聚合了 Steamer / ZiPS / THE BAT X / ATC 多系统，数据更全面。

### 关于 FA 池

FA 池因联盟而异（你的联盟里谁没被选就是 FA），没有统一公开数据源。当前提供两种方式：

1. **内置示例数据**（5 名球星，用于演示）
2. **CSV 导入**（从你的联盟平台导出 FA 列表）

全自动对接 ESPN/Yahoo 联盟 API 的功能在 `TODO.md` 中记录，后续实现。

---

## 7. 核心算法与评分逻辑

### 7.1 VORP 计算

**VORP（Value Over Replacement Player）**：球员相对于"替代水平球员"的价值。

**打者评分**：

```
score = R*权重 + HR*权重 + RBI*权重 + SB*权重 + AVG*权重
```

（权重来自 `config.yaml` 的 `league.scoring.hitters`）

**替代水平**：每个位置的 25 分位数（即同位置后 25% 的平均水本）。

```
vorp = score - 替代水平
```

**投手评分**：

```
score = W*权重 + SV*权重 + HOLD*权重 + ERA*权重 + WHIP*权重 + K_per_9*权重
```

（ERA/WHIP 权重设为负值，越低越好）

投手的替代水平是**全体投手的 25 分位数**。

### 7.2 SGP（Standings Gain Points）

与 VORP 并行的另一种评分体系，专为 **5×5 Roto 联盟**设计。

**核心思想**：计算每个球员在**每个统计类别**上能让你"升几名"（standings points），再求和。

**计数统计**（R/HR/RBI/SB/W/SV/K）：直接除以 SGP 分母。
```
SGP_HR = 球员预测HR / 10.4
```

**比率统计**（AVG/ERA/WHIP）：按球员对"假想团队均值"的实际拉动计算。
```
SGP_AVG = ((球员H + 1768) / (球员AB + 6617) - 0.267) / 0.0024
```

**SGP 分母**（12 队联盟经验值，可在 config.yaml 调整）：

| 打者类别 | 分母 | 投手类别 | 分母 |
|----------|------|----------|------|
| R | 24.6 | W | 3.03 |
| HR | 10.4 | SV | 9.95 |
| RBI | 24.6 | K | 39.3 |
| SB | 9.4 | ERA | -0.076 |
| AVG | 0.0024 | WHIP | -0.015 |

**综合**：
```
TotalSGP = SGP_R + SGP_HR + SGP_RBI + SGP_SB + SGP_AVG   （打者）
TotalSGP = SGP_W + SGP_SV + SGP_K + SGP_ERA + SGP_WHIP    （投手）
```

**VORP vs SGP 对比**：

| 维度 | VORP | SGP |
|------|------|-----|
| 评分逻辑 | 线性加权 | 按类别算"升几名" |
| 比率统计 | AVG 贡献≈0 | 正确处理（按团队拉动） |
| 适合赛制 | 通用简化 | 5×5 Roto |
| 使用命令 | `rank --method vorp` | `rank --method sgp` |

**使用建议**：两种指标并存，排名 CSV 分别输出。5×5 Roto 联盟推荐看 SGP；其他赛制看 VORP。

### 7.3 风险模型

`risk_model.method: "z_score"`（默认）：

```
vorp_upside = vorp + std_dev * adjustment_factor
vorp_floor  = vorp - std_dev * adjustment_factor   （不低于 0）
```

- `vorp_upside`：乐观预期（上限）
- `vorp_floor`：悲观预期（下限）
- `adjustment_factor`：默认 0.1，值越大风险影响越大

### 7.3 蒙特卡洛模拟

给每个球员的 ADP 加正态噪声，模拟多次选秀，统计每个球员被选中的概率和平均轮次。

- 噪声标准差：8.0（模拟 ADP 的自然波动）
- 加速：numba njit（10,000 次模拟约 4 秒）

### 7.4 FA 综合价值

```
综合价值 = 位置调整值 * 0.30
         + 趋势分 * 0.15
         + Statcast 评分 * 0.25
         + 位置调整值 * 0.30（VORP 权重，暂用位置值代替）
```

**趋势分**：近 10 场表现 vs 赛季均值。

- 100 = 与赛季持平
- 大于 100 = 近期上升
- 小于 100 = 近期下降

**伤病调整**：

| 严重度 | 系数 | 来源 |
|--------|------|------|
| mild（10-day IL） | 0.85 | MLB transactions |
| moderate（15-day IL） | 0.65 | |
| severe（60-day IL） | 0.40 | |
| long_term（赛季报销） | 0.15 | |

### 7.5 位置稀缺性

打者基础分按位置乘以稀缺系数：

| 位置 | 系数 | 说明 |
|------|------|------|
| C | 1.30 | 捕手最稀缺 |
| SS | 1.20 | |
| 2B | 1.10 | |
| 3B | 1.05 | |
| SP | 1.00 | 基准 |
| RP | 1.15 | |
| 1B | 0.90 | |
| OF | 0.85 | 外野最不稀缺 |

---

## 8. 配置文件（config.yaml）详解

```yaml
# ===== 数据处理 =====
data:
  use_multi_source: true          # 多源预测融合（仅 CSV 导入模式有效）
  file_patterns:                  # CSV 文件名模板
    hitters: "hitters_2026_{source}.csv"
    pitchers: "pitchers_2026_{source}.csv"
  positions_file: "data/player_positions_2025.csv"  # 位置映射（网络获取时不需要）

# ===== 预测源权重（仅 CSV 多源模式有效）=====
projections:
  weights:                        # 权重和必须为 1.0
    STEAMER: 0.7
    ZIPS: 0.3
  sources:
    - STEAMER
    - ZIPS

# ===== 联盟规则 =====
league:
  size: 12                        # 联盟队伍数
  rounds: 15                      # 选秀轮数
  roster_slots:                   # 阵容槽位
    C: 1
    1B: 1
    2B: 1
    3B: 1
    SS: 1
    OF: 4
    SP: 4
    RP: 3
    UTIL: 1
  scoring:
    hitters:                      # 正值=加分，负值=减分
      R: 1
      HR: 1
      RBI: 1
      SB: 1
      AVG: 1                      # 如需用 OBP，注释 AVG，取消 OBP: 1 注释
    pitchers:
      W: 1
      SV: 1
      HOLD: 1
      ERA: -1                     # 越低越好，所以设负值
      WHIP: -1
      K_per_9: 1

# ===== 选秀策略 =====
draft_simulator:
  default_strategy: "balanced"    # conservative / balanced / aggressive
  show_value_picks: true          # 标记价值股
  adp_file: "adp.csv"             # ADP 缓存文件

# ===== 风险模型 =====
risk_model:
  method: "z_score"               # z_score / historical_variance
  adjustment_factor: 0.1          # 风险调整系数

# ===== FA 分析 =====
fa_analyzer:
  update_frequency: 6             # 数据更新频率（小时）
  default_top_n: 10
  algorithm:
    position_weight: 0.3
    performance_weight: 0.4
    risk_weight: 0.2
    opportunity_weight: 0.1
  cache:
    expiry: 24                    # 缓存过期时间（小时）
    directory: "data/cache"
```

---

## 9. 常见使用场景

### 场景一：选秀前准备

```bash
# 1. 获取数据
python -m fantasy_baseball fetch-projections --season 2026
python -m fantasy_baseball rank
python -m fantasy_baseball adp

# 2. 看排名（打开生成的 fantasy_draft_rankings_vorp_2026.csv）

# 3. 模拟你在不同顺位的表现
python -m fantasy_baseball draft --pick 3 --strategy balanced
python -m fantasy_baseball draft --pick 8 --strategy balanced
python -m fantasy_baseball draft --pick 12 --strategy balanced

# 4. 挖 Sleeper
python -m fantasy_baseball sleeper --min-adp 100 --max-adp 350

# 5. 蒙特卡洛看哪些球员能活到你的顺位
python -m fantasy_baseball simulate --user-pick 5 --min-availability 0.30
```

### 场景二：赛季中 FA 挑选

```bash
# 1. 导入你的阵容（从选秀日志）
python -m fantasy_baseball roster import draft_log_pick5_balanced.csv

# 2. 更新数据
python -m fantasy_baseball fa update-injury --days-back 30

# 3. 导入你的联盟 FA 池（如果有 CSV）
python -m fantasy_baseball fa import-pool --file my_league_fa.csv

# 4. 生成推荐（会优先填补你阵容的缺口位置）
python -m fantasy_baseball fa recommend --risk balanced --top 10

# 5. 查某个 FA 目标的真实数据
python -m fantasy_baseball mlb "Tyler Glasnow" --season 2025 --statcast
```

### 场景三：换联盟规则重新分析

编辑 `config.yaml`，比如换成 OBP 联盟：

```yaml
  scoring:
    hitters:
      R: 1
      HR: 1
      RBI: 1
      SB: 1
      # AVG: 1    # 注释掉
      OBP: 1      # 改用 OBP
```

重新生成排名：

```bash
python -m fantasy_baseball rank
```

---

## 10. 常见问题（FAQ）

### Q: 启动报错 "No module named 'fantasy_baseball'"

**A**: 确保安装或设置了路径：

```bash
pip install -e .          # 方式A
# 或
export PYTHONPATH=src     # 方式B（Windows: set PYTHONPATH=src）
```

### Q: GUI 启动后选项卡显示"加载失败"

**A**: 通常是某个 tab 模块 import 出错。查看终端的错误日志，或用命令行方式运行查看完整报错。

### Q: 网络获取数据失败

**A**: 检查网络连接。所有数据源失败时会降级到 mock 数据，工具仍可使用但分析结果不准确。具体数据源的连通性测试：

```bash
python -m fantasy_baseball adp --force       # 测试 FantasyPros
python -m fantasy_baseball mlb "Mike Trout"  # 测试 MLB Stats API
```

### Q: 蒙特卡洛模拟很慢

**A**: 安装 numba 加速：

```bash
pip install numba
```

安装后 10,000 次模拟约 4 秒。

### Q: FA 推荐认为所有位置都缺人

**A**: 阵容未导入。先在「阵容验证」tab 导入阵容（从选秀日志），或在命令行：

```bash
python -m fantasy_baseball roster import draft_log_pick5_balanced.csv
python -m fantasy_baseball roster show    # 确认阵容已导入
```

### Q: 如何用 OBP 替代 AVG

**A**: 编辑 `config.yaml`，在 `scoring.hitters` 里注释 `AVG`、取消 `OBP` 注释。或用 GUI 的配置设置 tab 直接改。

### Q: 数据库损坏怎么办

**A**: 删除数据库文件，程序会自动重建空表：

```bash
rm fantasy_baseball.db
python -m fantasy_baseball fetch-projections --season 2026   # 重新填充
```

### Q: 支持 Keeper / Dynasty 联盟吗

**A**: 当前为 Redraft 联盟设计。Keeper 联盟需要额外的保留球员逻辑（在 `TODO.md` 的未来计划中）。

---

## 11. 离线使用与故障排除

### 完全离线模式

无网络时，工具仍可运行但数据有限：

- ADP：降级到 25 条内置 mock
- 球员统计/Statcast：降级到 mock 数据
- 预测数据：需提前用本地 CSV 导入

**离线准备步骤**：

1. 联网时运行 `fetch-projections` 和 `adp` 获取并缓存数据
2. 数据缓存在 `data/cache/` 目录和 `adp.csv` / `fantasy_baseball.db`
3. 断网后仍可使用缓存的排名和 ADP 进行选秀模拟

### 数据缓存位置

| 缓存 | 位置 | 说明 |
|------|------|------|
| ADP | `adp.csv` | 12 小时过期 |
| 球员统计 | `data/cache/hitter_*.json` | 6 小时过期 |
| Statcast | `data/cache/sc_*.json` | 24 小时过期 |
| 伤病 | `data/cache/injuries_*.json` | 6 小时过期 |
| 预测 | `fantasy_baseball.db` 的 `*_merged` 表 | 不自动过期 |

### 清除缓存

```bash
# 清所有缓存
rm -rf data/cache/
rm adp.csv

# 重新获取
python -m fantasy_baseball adp --force
```

### 数据库表结构

| 表 | 说明 |
|------|------|
| `hitters` / `pitchers` | 原始预测（多源时每源一行） |
| `hitters_merged` / `pitchers_merged` | 融合后的预测（用于排名） |
| `player_positions` | 球员位置映射 |
| `fa_pool` | FA 自由球员池 |
| `user_roster` | 用户阵容 |
| `injury_reports` | 伤病报告 |
| `player_season_stats` | 球员赛季统计（长表） |

---

## 12. 项目架构（开发者参考）

```
fbtool/
├── src/fantasy_baseball/          # 主包
│   ├── __main__.py                # 入口：python -m fantasy_baseball
│   ├── cli.py                     # 命令行子命令（13 个）
│   ├── config.py                  # 统一配置（加载/校验/保存）
│   ├── db/                        # 数据库层
│   │   ├── connection.py          #   连接管理 + db_session()
│   │   ├── schema.py              #   建表 + 迁移
│   │   └── repositories.py        #   仓储模式（PlayerRepo/FaRepo/...）
│   ├── core/                      # 核心业务
│   │   ├── scoring.py             #   VORP + 风险计算
│   │   ├── ingestor.py            #   CSV/Web → DB
│   │   ├── draft.py               #   蛇形选秀
│   │   ├── monte_carlo.py         #   蒙特卡洛（numba 加速）
│   │   ├── sleeper.py             #   Sleeper 推荐
│   │   ├── adp.py                 #   ADP 抓取（FantasyPros）
│   │   └── roster_validator.py    #   阵容验证
│   ├── fa/                        # FA 分析
│   │   ├── analyzer.py            #   价值计算
│   │   ├── real_time.py           #   实时数据
│   │   └── recommendation.py      #   推荐系统
│   ├── data_fetch/                # 数据抓取
│   │   ├── mlb_api.py             #   MLB Stats API（统计/伤病/趋势）
│   │   ├── statcast.py            #   Baseball Savant（Statcast 聚合）
│   │   └── projections.py         #   FantasyPros 预测
│   ├── plugins/                   # 插件系统
│   ├── gui/                       # 图形界面
│   │   ├── app.py                 #   主窗口 + run_async
│   │   └── tabs/                  #   10 个选项卡
│   └── utils/                     # 日志
├── tests/                         # 单元测试（121 个）
├── config.yaml                    # 配置文件
├── data/                          # 输入 CSV + 缓存
├── legacy/                        # 旧版脚本（归档参考）
├── pyproject.toml                 # 包定义
├── TODO.md                        # 待办（P4 联盟 API 对接）
└── USER_GUIDE.md                  # 本文档
```

### 测试

```bash
python -m pytest tests/ -q          # 运行全部 121 个测试
python -m pytest tests/test_regression.py -v  # 仅数值回归
```

---

*Fantasy Baseball Pro v2026.1.0 — 让每一次选择都建立在数据之上。*
