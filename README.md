# ⚾ Fantasy Baseball Pro（2026 赛季 · 重构版）

> **标准 Python 包结构 · 配置驱动 · 多模型融合 · 风险感知 · 阵容合规 · 图形界面 · CLI**

一套为严肃 Fantasy Baseball 玩家打造的专业级分析与选秀模拟系统。本项目在
2026.1.0 版本完成了全面重构：统一了分散在多个脚本中的重复逻辑（3 套 VORP → 1 套、
2 套配置 → 1 套、5 份 DB 连接样板 → 仓储模式），GUI 全部改为直接调用（不再 subprocess），
并补齐了项目卫生与测试。

---

## ✨ 重构亮点

| 旧版（v2026.0） | 新版（v2026.1） |
|--------|--------|
| 15 个顶层脚本各自为战 | 标准 `src/` 包结构，统一 `fantasy_baseball` 包 |
| 3 套 VORP 实现、2 套配置系统 | 单一来源：`core.scoring` + `config` |
| 5 个类各自复制 connect_db | 仓储模式 + `db_session()` 上下文管理 |
| GUI 用 subprocess 调 18 处脚本 | GUI 直接 import 业务模块，`run_async` 异步 |
| 14 处 sys.path.append hack | 包内绝对 import，零 sys.path hack |
| scoring/ 子包是死代码 | 逻辑统一到 `core/`，死代码归档到 `legacy/` |
| 无 .gitignore，.pyc/.db/.log 被跟踪 | 干净的 .gitignore，产物不再跟踪 |
| 测试有 3 个 broken | 48 个测试全绿 |

---

## 📂 项目结构

```
fbtool/
├── src/fantasy_baseball/          # 主包
│   ├── __main__.py                # python -m fantasy_baseball 入口
│   ├── cli.py                     # 命令行子命令
│   ├── config.py                  # 统一配置（单一来源）
│   ├── db/                        # 数据库层（连接 + 仓储）
│   │   ├── connection.py          #   db_session() / get_connection()
│   │   ├── schema.py              #   集中建表
│   │   └── repositories.py        #   PlayerRepo / FaRepo / ...
│   ├── core/                      # 核心业务逻辑
│   │   ├── scoring.py             #   VORP + 风险（唯一实现）
│   │   ├── ingestor.py            #   CSV → DB（向量化）
│   │   ├── draft.py               #   蛇形选秀（单次）
│   │   ├── monte_carlo.py         #   蒙特卡洛模拟（5 种 AI 策略）
│   │   ├── sleeper.py             #   Sleeper 推荐（v1+v2 合并）
│   │   ├── adp.py                 #   ADP 缓存
│   │   └── roster_validator.py    #   阵容验证
│   ├── fa/                        # FA 自由球员分析
│   ├── data_fetch/                # Statcast / 伤病 抓取
│   ├── plugins/                   # 插件系统
│   ├── gui/                       # 图形界面
│   │   ├── app.py                 #   主窗口 + run_async
│   │   └── tabs/                  #   9 个选项卡，直接 import
│   └── utils/                     # 日志等
├── tests/                         # 单元测试（138 个）
├── config.yaml                    # 配置文件（核心）
├── data/                          # 输入 CSV
├── legacy/                        # 旧版脚本（已归档，仅供参考）
├── docs/                         # 技术设计文档（TECHNICAL_DESIGN.md）
├── pyproject.toml                 # 包定义 + 依赖
└── requirements.txt
```

---

## 🚀 快速开始

### Windows 用户（最简单）

双击项目根目录的批处理即可：

- **`run_gui.bat`** —— 启动图形界面
- **`run_cli.bat`** —— 命令行交互菜单（14 项常用操作，带参数提示，输 0 退出）

**免安装便携模式**：两个 bat 会自动探测项目内的 `runtime\`（嵌入式 Python
+ pandas/numpy/PyYAML + tkinter，约 160MB）。把整个项目文件夹拷到**没有
安装 Python** 的电脑上，双击 bat 即可直接运行；开发机上没有 runtime 时
自动回落到系统 Python。runtime 为二进制不入 git，组装方法：
下载 [Python 3.7.9 嵌入式包](https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip)
解压到 `runtime/`，按 `runtime/python37._pth` 启用 site-packages 与 `..\src`，
get-pip 后 `pip install "pandas<1.4" "numpy<1.22" pyyaml`，再从本机 Anaconda
拷入 `DLLs/_tkinter.pyd`、`tcl86t.dll/tk86t.dll/zlib1.dll`、`Lib/tkinter`、
`tcl/tcl8.6` 与 `tcl/tk8.6`（bat 已设置 TCL_LIBRARY/TK_LIBRARY）。

### 安装

```bash
# 方式 A：可编辑安装（推荐，注册 fantasy-baseball 命令）
pip install -e .

# 方式 B：仅设置 PYTHONPATH（无需安装）
export PYTHONPATH=src   # Windows: set PYTHONPATH=src
```

### 准备数据

**预测数据会自动从网络获取**（FantasyPros，聚合 Steamer/ZiPS/THE BAT X/ATC）：

```bash
python -m fantasy_baseball fetch-projections
```

这会抓取 800+ 打者 + 900+ 投手的真实预测，同时自动填充位置映射。无需手动下载任何 CSV。

> **离线备选**：若网络不可用，可手动把 CSV 放到 `data/` 目录（文件名遵循 config.yaml 配置），用 `python -m fantasy_baseball ingest` 导入。

### 使用 GUI

```bash
python -m fantasy_baseball          # 启动图形界面
# 或
fantasy-baseball gui                # 安装后可用
```

9 个选项卡：首页 / 数据管理 / 配置设置 / 分析流水线 / 选秀中心 / 阵容验证 /
Sleeper 挖掘 / FA 分析 / 数据探索。（插件系统保留，界面入口暂时屏蔽）

排名 CSV、选秀日志、FA 导出统一输出到 `output/` 目录。

### 使用命令行

```bash
# 完整流水线（推荐：网络自动获取）
python -m fantasy_baseball fetch-projections  # 1. 抓取真实预测（--season 可省略，默认当前赛季）
python -m fantasy_baseball rank            # 2. 生成 VORP 排名
python -m fantasy_baseball adp             # 3. 准备 ADP

# 或从本地 CSV 导入（离线备选）
python -m fantasy_baseball ingest

# 选秀模拟
python -m fantasy_baseball draft --pick 5 --strategy balanced
python -m fantasy_baseball simulate --user-pick 5 --min-availability 0.25

# 其他
python -m fantasy_baseball sleeper --min-adp 80 --max-adp 300
python -m fantasy_baseball validate output/draft_log_pick5_balanced.csv --analyze
python -m fantasy_baseball fa update-fa     # 更新 FA 池
python -m fantasy_baseball fa recommend     # 生成 FA 推荐
```

---

## ⚙️ 配置（config.yaml）

所有联盟规则、评分权重、策略都集中在 `config.yaml`，可用 GUI 的「配置设置」选项卡
或直接编辑：

```yaml
league:
  size: 12
  rounds: 15
  roster_slots:
    C: 1, 1B: 1, 2B: 1, 3B: 1, SS: 1, OF: 4, SP: 4, RP: 3, UTIL: 1
  scoring:
    hitters:  {R: 1, HR: 1, RBI: 1, SB: 1, AVG: 1}
    pitchers: {W: 1, SV: 1, HOLD: 1, ERA: -1, WHIP: -1, K_per_9: 1}

projections:
  weights: {STEAMER: 0.7, ZIPS: 0.3}   # 权重和必须为 1.0

draft_simulator:
  default_strategy: "balanced"          # conservative / balanced / aggressive

risk_model:
  method: "z_score"                     # z_score / historical_variance
```

---

## 🧠 核心功能

| 功能 | 说明 |
|------|------|
| **多源预测融合** | Steamer / ZiPS / THE BAT 按权重加权平均 |
| **VORP + 风险模型** | vorp / vorp_upside / vorp_floor 三维评估 |
| **蛇形选秀模拟** | 三种策略，智能槽位分配，价值股标记 |
| **蒙特卡洛模拟** | 5 种 AI 经理策略，1000+ 次模拟估算球员可用概率 |
| **Sleeper 挖掘** | VORP vs ADP 偏差，可选 Statcast 信号增强 |
| **FA 分析** | 赛季中自由球员推荐（综合价值 + 阵容需求 + 风险） |
| **阵容验证** | 合规性检查 + 强度分析（已修复除零 bug） |

---

## 🧪 测试

```bash
python -m pytest tests/ -q            # 运行全部 48 个测试
```

覆盖：配置、数据库、评分、导入、选秀（蛇形+蒙特卡洛）、阵容验证、FA 分析。

---

## 🔧 依赖

```bash
pip install -r requirements.txt       # 核心：pandas, numpy, pyyaml
```

可选依赖：
- `numba`（蒙特卡洛加速，未安装自动降级为纯 Python）
- `requests`（Statcast/伤病在线抓取，未安装可用 mock 数据）

---

## 📜 从旧版迁移

- 旧版所有脚本归档在 `legacy/`，仍可单独运行查看旧逻辑
- 数据库 schema 保持兼容，现有 `fantasy_baseball.db` 可继续使用
- `config.yaml` 格式不变，直接复用

---

## 📊 数据源说明

全部数据源免费、无需 API key：

| 数据 | 来源 | 说明 |
|------|------|------|
| **预测数据** | [FantasyPros](https://www.fantasypros.com/mlb/projections/) | 真实抓取，聚合 Steamer/ZiPS/THE BAT X/ATC，800+ 打者 + 900+ 投手。同时自动填充位置映射。 |
| **ADP** | [FantasyPros](https://www.fantasypros.com/mlb/adp/overall.php) | 真实抓取，聚合 Yahoo/CBS/NFBC/ESPN，约 600 名球员。12 小时缓存。无网络时降级到 mock。 |
| **球员赛季统计** | [MLB Stats API](https://statsapi.mlb.com) | 真实数据（AVG/HR/RBI/W/ERA/K/9 等）。6 小时缓存。 |
| **Statcast** | [Baseball Savant](https://baseballsavant.mlb.com) | 真实逐投球数据聚合（exit velocity/xwOBA/barrel%/whiff% 等）。24 小时缓存。 |
| **伤病动态** | [MLB Stats API](https://statsapi.mlb.com) transactions | 真实伤病列表（含严重度分级），从 IL 动态解析。 |

所有真实数据源失败时优雅降级到内置 mock，保证离线环境工具仍可用。

### 查询球员真实数据

```bash
# 查询球员赛季统计 + Statcast
python -m fantasy_baseball mlb "Aaron Judge" --season 2025 --statcast

# 仅查询统计
python -m fantasy_baseball mlb "Shohei Ohtani"

# 更新真实伤病数据（回溯 60 天）
python -m fantasy_baseball fa update-injury --days-back 60

# 强制刷新 ADP
python -m fantasy_baseball adp --force
```

GUI 的「Statcast」选项卡支持按姓名查询，「FA 分析」选项卡的更新按钮会拉取真实伤病。

---

## 📄 许可证

MIT License — 自由使用、修改、分发。
