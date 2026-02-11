# ⚾ Fantasy Baseball Pro 工具链（2026 赛季 · 离线增强版）

> **100% 离线 · 配置驱动 · 多模型融合 · 风险感知 · 阵容合规 · 图形界面**

一套为 **严肃 Fantasy Baseball 玩家** 打造的专业级分析与选秀模拟系统。  
无需网络、不依赖 `pybaseball`、不受反爬限制，所有逻辑透明可控，结果高度可复现。

---

## ✨ 为什么选择本工具链？

| 传统方案 | 本工具链 |
|--------|--------|
| 自动抓取 → 常被封 IP | ✅ **手动 CSV + 离线处理** |
| 单一预测源 → 偏差大 | ✅ **Steamer + ZiPS + THE BAT 多源融合** |
| 仅期望值 → 忽略波动 | ✅ **VORP + Upside/Floor 风险模型** |
| 规则硬编码 → 难修改 | ✅ **`config.yaml` 一键切换联盟规则** |
| 选秀后才发现超编 | ✅ **自动阵容合规检查器** |
| 手动编辑配置 → 易出错 | ✅ **交互式配置工具** |
| 命令行操作 → 不直观 | ✅ **图形用户界面 (GUI)** |

---

## 📂 项目结构
fantasy-baseball-pro/
├── config.yaml # ← 主配置文件（核心！）
├── config_loader.py # 配置加载工具
├── interactive_config.py # 交互式配置工具
├── gui_app.py # 图形用户界面
│
├── ingest_manual_csv_to_db.py # → 导入 CSV（支持多源）
├── fantasy_scoring_model_v2.py # → 生成带风险评分的 VORP 排名
├── snake_draft_simulator_pro.py # → 模拟蛇形选秀（价值股提示）
├── fetch_adp_cached.py # → （可选）缓存 ADP
├── validate_roster.py # → 验证阵容是否合规
│
├── data/ # ← 手动下载的 CSV 目录
│ ├── hitters_2026_steamer.csv # 示例：多源命名
│ ├── hitters_2026_zips.csv
│ ├── pitchers_2026_steamer.csv
│ ├── pitchers_2026_zips.csv
│ └── player_positions_2025.csv # 必需：球员位置映射
│
├── tests/ # → 测试文件目录
│ ├── test_config_loader.py
│ └── test_data_ingestor.py
│
├── requirements.txt # → 依赖项
├── fantasy_baseball.db # 自动生成的数据库
├── fantasy_draft_rankings_vorp_2026.csv # 生成的排名（含风险列）
├── adp.csv # （可选）ADP 文件
└── draft_log_pick5_balanced.csv # 选秀日志示例

---

## 🚀 快速开始

### 方式 A：使用图形用户界面（推荐）

```bash
python gui_app.py
```

GUI 界面提供了所有功能的可视化操作，包括：
- 数据管理：导入和管理 CSV 数据
- 配置设置：调整联盟规则和选秀策略
- 分析流水线：运行完整的分析流程
- 选秀模拟：模拟蛇形选秀过程
- 阵容验证：检查阵容合规性

### 方式 B：使用命令行工具

#### 第 1 步：准备数据

从 [FanGraphs Projections](https://www.fangraphs.com/projections.aspx) 下载以下 CSV 到 `data/`：

- **打者预测**（任选一种或多种）：
  - `hitters_2026.csv`（单源）
  - 或 `hitters_2026_steamer.csv`, `hitters_2026_zips.csv`（多源）
- **投手预测**（同上）：
  - `pitchers_2026.csv` 或多源变体
- **历史数据**（用于趋势参考）：
  - `hitters_2024.csv`, `hitters_2025.csv`
  - `pitchers_2024.csv`, `pitchers_2025.csv`
- **位置映射**（必需！）：
  - 从 [FanGraphs 打者排行榜 (2025)](https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=8&season=2025) 导出 CSV，确保含 `Name` 和 `POS` 列，保存为 `player_positions_2025.csv`

> 💡 **命名规范**：若启用多源，请在 `config.yaml` 中配置模板。

#### 第 2 步：配置你的联盟规则

有两种方式配置联盟规则：

##### 方式 A：使用交互式配置工具（推荐）

```bash
python interactive_config.py
```

按照提示逐步配置数据处理、预测源权重、联盟规则、选秀策略等参数。

##### 方式 B：手动编辑配置文件

编辑 `config.yaml`（关键参数说明）：

```yaml
# 启用多源融合？
data:
  use_multi_source: true

# 权重分配（总和=1.0）
projections:
  weights:
    STEAMER: 0.7
    ZIPS: 0.3

# 联盟规模与阵容
league:
  size: 12
  rounds: 15
  roster_slots:
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
    hitters:
      R: 1, HR: 1, RBI: 1, SB: 1, AVG: 1
    pitchers:
      W: 1, SV: 1, HOLD: 1, ERA: -1, WHIP: -1, K_per_9: 1

# 选秀策略
draft_simulator:
  default_strategy: "balanced"  # conservative / balanced / aggressive
```

📌 提示：想用 OBP？注释 AVG，取消 OBP: 1 注释。

#### 第 3 步：运行分析流水线

```bash
# 1. 导入数据（自动融合多源）
python ingest_manual_csv_to_db.py

# 2. 生成带风险评分的排名
python fantasy_scoring_model_v2.py

# 3. （可选）获取最新 ADP（首次需联网）
python fetch_adp_cached.py --force

# 4. 模拟选秀（第5顺位，使用 config.yaml 中的策略）
python snake_draft_simulator_pro.py --pick 5
```

✅ 输出：
- `fantasy_draft_rankings_vorp_2026.csv`（新增 vorp_upside, vorp_floor 列）
- `draft_log_pick5_balanced.csv`（含价值股 💎 标记）

#### 第 4 步：验证阵容（防超编）

```bash
python validate_roster.py draft_log_pick5_balanced.csv
```

输出示例：

```text
📋 阵容合规性检查:
✅ C: 1/1
✅ SS: 1/1
⚠️ 2B: 0/1 → 建议将 Bregman (UTIL) 移至 2B
✅ SP: 4/4
...
❗ 阵容不完整，请调整！
```

---

## 🧠 高级功能详解

### 1. 多源预测融合
- 支持任意数量预测源（Steamer/ZiPS/THE BAT）
- 自动按权重加权平均统计项（HR, ERA, K 等）
- 配置简单：只需改 config.yaml + 按模板命名文件

### 2. 风险-回报模型
- **aggressive** 策略：优先选 vorp_upside 高的新秀（如 Witt Jr）
- **conservative** 策略：优先选 vorp_floor 稳的老将（如 Goldschmidt）
- **balanced** 策略：使用标准 VORP

### 3. ADP 缓存机制
- `fetch_adp_cached.py` 首次联网抓取，后续读缓存
- 主流程（1-4 步）完全离线，ADP 仅为增强功能

### 4. 智能槽位分配
- 自动处理 C/SS/UTIL/OF 等复杂位置
- 避免"OF 满了但 2B 空着"的常见错误

### 5. 交互式配置工具
- 图形化界面配置联盟规则
- 实时验证配置有效性
- 减少手动编辑 YAML 的错误

### 6. 图形用户界面
- 直观的选项卡式界面
- 所有功能的可视化操作
- 实时状态更新和日志显示
- 适合不熟悉命令行的用户

---

## ⚙️ 依赖安装

```bash
pip install -r requirements.txt
```

✅ 核心依赖：
- pandas
- pyyaml
- numpy

✅ GUI 依赖：
- tkinter（Python 标准库，无需单独安装）

✅ 可选依赖（用于 ADP 获取）：
- requests
- beautifulsoup4
- lxml

---

## ❓ 常见问题

**Q: 如何导入数据？**
A: 在数据管理选项卡中选择CSV文件，然后点击导入数据按钮。

**Q: 如何配置联盟规则？**
A: 在配置设置选项卡中调整联盟规模、阵容槽位等参数，然后点击保存配置按钮。

**Q: 如何运行选秀模拟？**
A: 在选秀模拟选项卡中设置选秀顺位和策略，然后点击模拟选秀按钮。

**Q: 如何验证阵容？**
A: 在阵容验证选项卡中选择选秀日志文件，然后点击验证阵容按钮。

**Q: 如何查看分析结果？**
A: 在分析流水线选项卡中运行分析步骤，然后在排名结果中查看生成的排名文件。

**Q: GUI 应用无法启动怎么办？**
A: 确保你的系统安装了 tkinter 库（Python 标准库，通常默认安装）。如果问题仍然存在，请尝试使用命令行工具。

---

## 📜 许可证

MIT License — 自由使用、修改、分发。

---

## ✅ 这个 README 的优势

- **新手友好**：四步流程清晰，附带截图式目录
- **专业深度**：解释多源融合、风险模型等核心创新
- **即插即用**：复制到项目根目录即可
- **强调离线**：突出与传统方案的本质差异
- **覆盖全部脚本**：从数据准备到阵容验证闭环
- **更新及时**：包含最新的图形用户界面等功能
