# 待办事项（TODO）

> 最后更新：2026-08-14
> 当前版本：2026.1.0 | 测试：135 passed | 已打包 Windows exe

---

## 🔴 高严重度 Bug（功能可用性审计 2026-08-14）

> ✅ 第一波已全部修复（2026-08-14）：
> - H1 蒙特卡洛按 method 返回 sgp_total/vorp 列（monte_carlo.py + draft_center.py）
> - H2 导出前 os.makedirs（recommendation.py）
> - H3 mock ADP 永不写盘（adp.py），新增测试验证不覆盖真实缓存
> - H4 player_id 为空时按姓名搜索 MLB id 兜底（recommendation.py）
> - H9 xera 键名兼容大小写（analyzer.py）
>
> 测试：135 passed（更新了 2 个 ADP 测试以匹配 H3 新行为）

<details>
<summary>原始发现记录（点击展开）</summary>

### H1 GUI 蒙特卡洛切到 SGP 必然崩溃
- **现象**：选秀中心把「评分方法」切到 SGP 再点「蒙特卡洛」，弹 KeyError: 'vorp'
- **原因**：`analyze_availability` 固定返回 vorp 列（monte_carlo.py:393），SGP 池没有 vorp 列
- **修复**：`analyze_availability` 按 method 返回 sgp_total 或 vorp ✅

### H2 FA「导出结果」100% 失败
- **现象**：点击导出报错，reports/ 目录不存在
- **原因**：recommendation.py:147 直接 to_csv 没有 os.makedirs
- **修复**：导出前 `os.makedirs(os.path.dirname(path), exist_ok=True)` ✅

### H3 离线时 mock ADP 污染真实缓存
- **现象**：离线运行后 25 条 mock 被写进 adp.csv，12 小时内联网也读 mock；GUI「准备ADP」force=True 会用 mock 覆盖真实数据
- **位置**：adp.py:293-298
- **修复**：mock 数据永不写盘（只驻留内存）✅

### H4 FA 池 CSV 留空 player_id → 推荐静默丢弃
- **现象**：文档说 player_id 可留空，导入成功但「生成推荐」永远空
- **原因**：recommendation.py:91-93 `pid is None → return None`
- **修复**：player_id 为空（None/NaN）时按姓名搜索 MLB id 兜底 ✅

### H9 所有投手 FA 评分被无差别扣 40 分
- **现象**：投手 Statcast 分中 xERA 项恒取默认值 5，贡献恒为 -40
- **原因**：analyzer.py:214 读 `xERA`（大写），statcast.py:213 存 `xera`（小写）
- **修复**：兼容两种大小写键名 ✅

</details>

---

## 🟡 中严重度（体验/一致性，2026-08-14）

> ✅ 第二波已修复（2026-08-14）：M1、M2、M3、M4、M10
> 待处理：M5、M6、M7、M8

### ✅ M1 GUI 阵容导入顺位硬编码为 5（已修复）
- 修复：roster tab 加「你的顺位」输入框，导入时按输入顺位提取阵容

### ✅ M2 CLI/GUI method 与参数不一致（已修复）
- 修复：CLI `fa recommend` 和 `simulate` 加 `--method vorp|sgp`

### ✅ M3 「更新伤病」断网仍报成功（已修复）
- 修复：网络失败抛 RuntimeError（GUI 显示错误框）；0 条时明确提示"该时段无伤病动态"

### ✅ M4 「取消」按钮无效（已修复）
- 修复：GUI 层任务完成时检查取消标志丢弃结果；纯 Python 蒙特卡洛循环支持 cancel_check 中断；FA 推荐循环支持取消

### ✅ M10 「数据探索」和 CLI mlb 默认查 2025 赛季（已修复）
- 修复：默认改为当前年（datetime.now().year），CLI --season 默认 None

### M5 Sleeper「启用Statcast增强」开关无效
- sleeper.py 读 data/statcast_batter_2025.csv，实际只有 statcast_data_sample.csv
- 修复：接真实 Statcast 缓存（data/cache/*.json）或禁用该开关并说明

### M6 配置 GUI 只能编辑一小部分
- 只能改 league 主项+默认策略；data/projections/risk_model/sgp/fa_analyzer/logging/scoring.stream_slots 全得手改 YAML
- 修复：分阶段补全配置 tab（或至少加 YAML 文本编辑器）

### M7 文档多处与现实不符
- README 说 13 选项卡（实际 10）；USER_GUIDE 说 13 子命令（实际 12）；"25 分位数"描述已过时（现在是动态替代水平）
- 修复：同步文档

### M8 输出文件散落根目录
- 排名 CSV/选秀日志/adp.csv/db/logs 全在根目录；同名选秀日志静默覆盖
- 修复：统一 output/ 目录 + 时间戳文件名

---

## 🟢 低严重度（2026-08-14）

- **L1** 选秀模拟重复执行两遍（draft_center.py:59-60 显示一次+保存一次）
- **L2** 错误信息中英混杂（中文按钮弹英文异常）
- **L3** `_safe_float` 把负数解析成正数（mlb_api.py:337 `replace("-","")`）
- **L4** SGP 选秀日志 vorp 全 0，阵容强度分析显示 0.00
- **L5** 文档细节出入（按钮表漏「查看排名」、符号描述不符）
- **L6** exe 不带 USER_GUIDE，GUI 首页却指向它
- **L7** 查看状态不含 FA 表行数；死 tab 文件（draft_tab/help_tab/injury/monte_carlo_tab/statcast）未清理

---

## 🌱 未来隐患

### H7 2026/2025 大面积硬编码
- 排名文件名 fantasy_draft_rankings_vorp_2026.csv、默认赛季 2026/2025、CSV 模板 *_2026.csv
- 2027 年将静默产出错误文件名 / 查两年前数据
- 修复：赛季参数化（config 加 season 字段，文件名动态生成）

---

## ⏸️ 已暂缓

### P4：联盟平台 API 对接
- **状态**：暂缓 — Yahoo 需要特殊网络条件才能访问
- **目标**：对接 ESPN / Yahoo 联盟 API，实现全自动 FA 池 + 用户阵容同步

#### 背景
当前 FA 池和用户阵容已支持 CSV 手动导入（P2 + P3 已完成），但要获得"自己联盟里谁没被选"的真实 FA 池，需要对接联盟平台。每个平台的 FA 池因联盟而异，没有统一公开数据源。

#### 需要做的事
1. **ESPN Fantasy API**（无官方认证，逆向工程，社区有成熟方案）
   - 端点：`lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{year}/...`
   - 拉取联盟 roster → 推算 FA 池（全量球员 - 已选球员）
   - 参考：`cwendt94/espn-api` Python 库

2. **Yahoo Fantasy API**（OAuth 2.0 认证）
   - 需注册 Yahoo Developer 应用获取 client_id/secret
   - 用户授权后拉联盟数据
   - 访问可能需要特殊网络条件（用户反馈）

3. **Sleeper API**（不支持棒球，仅 NFL/NBA/LCS）
   - 排除，不适用于本项目

#### 实施方案（待定）
- 新建 `data_fetch/league_api.py`，按平台分别实现
- GUI 加"绑定联盟"配置（输入联盟 ID + 平台）
- 定期同步 FA 池 + 用户阵容到数据库

#### 优先级
低 — 手动 CSV 导入已满足基本需求，全自动同步是锦上添花。

---

## ✅ 已完成项

以下在本次开发中已实现，记录在此供追溯：

### 2026-08-14 完成（评分算法最终版）
- [x] #5 类别平衡约束（选秀模拟给弱势类别球员 bonus，仅用户球队生效）
- [x] #4 多位置资格（提取 eligible_pos，VORP 取最优归属位置）
- [x] #3 SGP 分母按联盟规模动态调整（计数统计线性缩放，比率统计不变）
- [x] #2 动态替代水平（基于 league_size × (slots - stream_slots)，可配置 stream_slots）
- [x] #1 投手 SP/RP 分开算替代水平（scoring.py）
- [x] #6 SGP 接入蒙特卡洛模拟（monte_carlo.py + GUI 选秀中心）
- [x] #7 CLI draft 支持 --method 参数
- [x] #8 配置 tab 可编辑阵容槽位（config_tab.py）
- [x] #9 FA 推荐 tab 显示当前阵容缺口

### 2026-08-13 完成（打包 + SGP）
- [x] Windows exe 打包（PyInstaller，脱离 Python 环境）
- [x] GUI 启动最大化窗口
- [x] 选秀策略下拉框
- [x] SGP 评分模型（贯穿排名/选秀模拟/FA分析全链路）
- [x] VORP + SGP 双指标可切换
- [x] 真实趋势分（MLB gameLog 近 10 场 vs 赛季均值）
- [x] 蒙特卡洛 numba 加速（打包版纯 Python 降级）
- [x] GUI 现代化（直接 import、任务取消、排名预览）
- [x] 配置保存保留注释
- [x] user_roster 阵容管理（CLI + GUI）
- [x] FA 池 CSV 导入
- [x] 选项卡 13→10 合并
- [x] 完整帮助文档（USER_GUIDE.md）

### 2026-08-11 完成（重构核心）
- [x] 全面重构：src/ 包布局、仓储模式、统一配置、消除 sys.path hack
- [x] 真实数据源：FantasyPros 预测/ADP、MLB Stats API 统计/伤病/趋势、Baseball Savant Statcast
- [x] 测试 135 passed（含数值回归 + GUI + SGP）
- [x] 依赖版本锁定、Statcast mock 兜底、伤病 team 解析
