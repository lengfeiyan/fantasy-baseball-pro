# 待办事项（TODO）

> 最后更新：2026-08-17
> 当前版本：2026.1.0 | 测试：145 passed | 已打包 Windows exe

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
> ✅ 第三波已修复（2026-08-17）：M5、M6、M7、M8

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

### ✅ M5 Sleeper「启用Statcast增强」开关无效（已修复 2026-08-17）
- 修复：无显式 CSV 时通过 MLBStatsClient.search_player + StatcastFetcher 走真实 API（带 JSON 缓存）

### ✅ M6 配置 GUI 只能编辑一小部分（已修复 2026-08-17）
- 修复：配置 tab 新增价值股标记下拉框、stream 席位数、风险调整系数、SGP 分母（打者+投手）；新增构造测试

### ✅ M7 文档多处与现实不符（已修复 2026-08-17）
- 修复：README/USER_GUIDE 同步为 10 选项卡、12 子命令、动态替代水平、output/ 目录、赛季参数化

### ✅ M8 输出文件散落根目录（已修复 2026-08-17）
- 修复：新增 config.output_path()/find_output_file()，排名/选秀日志/FA 导出统一到 output/，读取端兼容旧根目录文件

---

## 🟢 低严重度（2026-08-14）

- ✅ **L1** 选秀模拟重复执行两遍（已修复：simulate_and_save 支持传入 log_df）
- ✅ **L2** 错误信息中英混杂（已修复：gui/errors.py friendly_error 统一翻译常见异常，4 个弹窗点接入）
- ✅ **L3** `_safe_float` 把负数解析成正数（已修复：保留负号，只剔除 "-/-.---/---" 占位符，新增回归测试）
- ✅ **L4** SGP 选秀日志 vorp 全 0（已修复：SGP 时 vorp 列回填 sgp_total；强度分析自动识别）
- ✅ **L5** 文档细节出入（已随 M7 同步修复）
- ✅ **L6** exe 不带 USER_GUIDE（已修复：fbtool.spec datas 加入 USER_GUIDE.md）
- ✅ **L7** 查看状态不含 FA 表行数；死 tab 文件（已修复：draft_tab/help_tab/injury/monte_carlo_tab/statcast 归档到 legacy/gui_tabs/）

---

## 🌱 未来隐患

### ✅ H7 2026/2025 大面积硬编码（已修复 2026-08-17）
- config 新增 `data.season` 字段（默认当前年）；排名文件名、抓取默认年份、CSV 模板动态生成
- CLI `--season` 默认 None（当前年）；`{season}` 占位符可用于 file_patterns

---

## 📋 待实施

### P4a：ESPN 联盟平台接入（FA 池 + 阵容自动同步）
- **状态**：方案已定稿，待实施 → 详见 [PLAN_P4_LEAGUE_PLATFORM.md](PLAN_P4_LEAGUE_PLATFORM.md)
- **结论**：ESPN Fantasy API v3 已实测可用（公开联盟免认证，私盟需 SWID/espn_s2 cookie）；统一 LeagueProvider 抽象同时覆盖 Yahoo
- **实施顺序**（8 步）：
  1. 用户机器 curl 验证 ESPN 连通性
  2. `data_fetch/league_api.py`（LeagueProvider 抽象 + ESPNProvider）+ `tests/test_espn.py`
  3. config 新增 `league_platform` 段 + GUI「联盟平台绑定」区
  4. `RealTimeData` 改造（FA 池同步走 ESPN / 新增阵容同步）+ GUI/CLI 接入
  5. 全套测试 + USER_GUIDE 文档 + 提交

### F1：模拟战绩榜（Projected Standings）★ 强烈推荐
- **价值**：SGP 体系的杀手级应用——把阵容各类别加总按 SGP 分母折算成预计名次积分，
  输出 12 队模拟战绩榜（"我这个阵容 HR 争第 2、SB 只能第 9"），比 VORP 总分直观一个量级
- **成本**：低（数据模型全有，纯展示层；选秀日志/用户阵容 → 各类别加总 → 分母折算 → 排名）

### F2：GUI 结果表格化（ttk.Treeview）★ 强烈推荐
- **价值**：排名/阵容/FA 推荐目前是等宽文本，换成可排序表格（点列头排序、选中看详情），
  日常使用体验提升最大
- **成本**：低-中（Treeview 组件 + 各 tab 替换输出区）

### F3：先发投手 Streaming 建议
- **价值**：VORP 已内置 stream_slots 理念，但没回答"今天该 stream 谁"——
  每日 probable starters（MLB API 有）+ 对手打线强弱 → 今日先发候选与对阵难度
- **成本**：中

### F4：交易评估器
- **价值**：赛季中高频场景；输入两边球员包，按 VORP/SGP 差值 + 位置缺口给出评估
- **成本**：低-中（复用现有评分）

### F5：逐周对手分析（H2H 联盟）
- **价值**：周赛制下分析未来一周对手强弱类别，调整先发策略（依赖 P4a 真实联盟数据）
- **成本**：中

### F6：SGP 分母自校准
- **价值**：现在的分母是 12 队经验值；导入用户联盟历史战绩可校准为自己联盟的分母
- **成本**：中

### E1：重打 Windows exe（打包成果已落后 20+ 提交，做完功能批次后执行）

---

## ⏸️ 已暂缓

### P4b：Yahoo 联盟平台 API 对接
- **状态**：暂缓 — 2026-08-17 已实测确认：Yahoo 自 2021-11-01 起屏蔽中国大陆 IP（curl 与真实浏览器均返回官方公告页），需代理 + OAuth 2.0
- **目标**：在 LeagueProvider 抽象下实现 YahooProvider（OAuth 2.0 认证 + `fantasysports.yahooapis.com`，XML 响应），挂上代理即可用
- **背景**：Yahoo Fantasy 需要注册 Developer 应用获取 client_id/secret，用户 OAuth 授权后拉联盟数据；网络层需支持 HTTP(S)_PROXY
- **其他平台**：Sleeper API 不支持棒球（仅 NFL/NBA/LCS），排除

#### 背景（整体）
当前 FA 池和用户阵容已支持 CSV 手动导入（P2 + P3 已完成），但要获得"自己联盟里谁没被选"的真实 FA 池，需要对接联盟平台。每个平台的 FA 池因联盟而异，没有统一公开数据源。

#### 优先级
中 — 手动 CSV 导入已满足基本需求，自动同步显著提升 FA 分析可用性（P4a/ESPN 先行）。

---

## ✅ 已完成项

以下在本次开发中已实现，记录在此供追溯：

### 2026-08-20 完成（数据统一入库）
- [x] DB 成为唯一当前数据源：新增 adp/rankings/draft_logs/fa_recommendations 四张表 + 四个仓储
- [x] ADP 管道：DB 优先（TTL 看 fetched_at）→ CSV 回退 → 抓取写库；CSV 有效且 DB 空时自动回填
- [x] 排名双写（VORP/SGP 按 method 快照替换）；Sleeper/分析页「查看排名」改 DB 优先
- [x] 选秀日志/FA 推荐会话式入库（一次模拟/推荐一个 session_id，支持历史对比）
- [x] CSV 降级为备份：output/history/ 时间戳文件（永不覆盖）+ output/ 同名"最近一次"
- [x] 阵容页新增「从最近模拟导入」按钮（直接读 DB 最新会话，无需选文件）
- [x] 测试 179 → 191 passed（新增 12 个管道测试 + isolated_db/isolated_history 隔离 fixture）

### 2026-08-18 完成（代码审计修复：11 高危 + 中危清理）
- [x] 高危 2 项（上轮改动引入）：save_config_values 跨段覆盖（SGP 分母改写评分权重，实测复现）；analysis.py 准备ADP NameError
- [x] 高危：VORP 替代水平分位数方向颠倒（quantile(1-q)）；SGP 缺列 fillna(0) 零产量（按定义反推 ER/K/H+BB/AB，反推不了记 NaN）
- [x] 高危：价值股标记方向反（reach↔滑落）；阵容验证全联盟口径（is_user_pick/team_id 过滤）
- [x] 高危：user_roster 外键死循环（去 FK，迁移只跑一次 + 恢复记日志 + busy_timeout 30s）
- [x] 高危：伤病解析三连错（activated 复出/转投取 to-the 天数/队名动词）；DH→UTIL 评分归零；蒙特卡洛 SGP 池 KeyError
- [x] 中危清理：GUI 轮询链容错（after 进 finally + error 回调包裹）、每任务独立取消信号、并发进度条计数、7 个 tab 跨线程 Tk 取值改 UI 线程
- [x] 中危清理：多源融合 NaN 权重归一化；负 VORP upside/floor 方向；statcast_score 恒饱和改相对分；need_factor 位置归一化（CF/DH/P）；风险偏好幂缩放真正生效
- [x] 中危清理：CLI import-pool 空参守卫；插件 sys.modules 前缀注册防劫持；fetch_injuries 网络失败抛异常（死代码激活）；mock 统计带 is_mock 标记（GUI 显示"示例数据"）
- [x] 中危清理：eligible_pos 多位置资格接线（schema+ingestor，曾为死代码）；类别平衡跨量纲归一化；Linux zoomed TclError 守卫
- 测试：145 → 178 passed（新增 33 个回归测试）

### 2026-08-18 完成（GUI 体验打磨，实测反馈驱动）
- [x] 任务期间全局忙碌反馈：手表光标 + 全窗口按钮禁用防重复点击（长任务 20-40s 曾可连点出并发任务）
- [x] 配置设置页展示不全：改双列布局 + Canvas 滚动（M6 补全后 7 区块 30+ 行输入框单列超屏）
- 测试：179 passed

### 2026-08-17 完成（第三波修复：剩余审计项）
- [x] L2 错误信息中文化（gui/errors.py friendly_error：常见网络/文件/数值异常→中文说明，附原始详情）
- [x] M5 Sleeper Statcast 走真实 API（无文件时 search_player + StatcastFetcher，带缓存）
- [x] M6 配置 GUI 补全：价值股标记、stream 席位数、风险调整系数、SGP 分母
- [x] M8 输出统一到 output/（config.output_path/find_output_file，读端兼容旧路径）
- [x] M7+L5 文档同步现实（10 选项卡/12 子命令/动态替代水平/output/）
- [x] L1 选秀模拟不再执行两遍（simulate_and_save 支持传入 log_df）
- [x] L3 _safe_float 保留负号（只剔除占位符），新增回归测试
- [x] L4 SGP 日志 vorp 回填 sgp_total，强度分析自动识别
- [x] L6 exe 打包携带 USER_GUIDE.md
- [x] L7 死 tab 文件归档 legacy/gui_tabs/；查看状态补充 fa_pool/injury_reports/user_roster 行数
- [x] H7 赛季参数化（config data.season，文件名/默认年份动态生成，支持 {season} 占位符）

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
