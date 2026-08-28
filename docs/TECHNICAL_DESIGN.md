# Fantasy Baseball Pro 技术设计文档

> 版本：2026.8 ｜ 配套代码：main 分支 ｜ 用户手册见 [USER_GUIDE.md](../USER_GUIDE.md)
>
> 本文档面向开发者与维护者，覆盖架构、算法、数据层、分发与测试。

---

## 1. 项目概览

**定位**：Fantasy Baseball（5×5 Roto / H2H）分析与选秀模拟工具。中文界面、离线可用、零外部服务依赖。

**功能矩阵**：

| 模块 | 能力 |
|------|------|
| 数据 | FantasyPros 预测（800+ 打者/900+ 投手）与 ADP；MLB Stats API 统计/伤病/趋势；Baseball Savant Statcast |
| 评分 | VORP（动态替代水平）与 SGP（5×5 类别增益）双体系，全链路可切换 |
| 选秀 | 蛇形模拟（策略/类别平衡/价值股）、蒙特卡洛可用性（numba 加速） |
| FA | 池管理、推荐（需求/风险/Statcast）、伤病跟踪 |
| Sleeper | ADP vs 模型排名偏差挖掘，Statcast 信号增强 |
| 分发 | Windows exe（PyInstaller）/ 便携运行时（嵌入式 Python，免安装） |

**技术栈**：Python 3.7+（开发环境 3.7，CI 验证 3.9/3.11）、tkinter、pandas、numpy、PyYAML、SQLite。numba/requests 为可选依赖（缺失自动降级）。

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────┐
│ 入口层  gui/app.py（tk 主窗口）     cli.py（12 子命令）│
│         run_gui.bat / run_cli.bat（便携探测）        │
├──────────────────────────────────────────────────┤
│ 业务层  core/   scoring/sgp/draft/monte_carlo/      │
│                sleeper/adp/ingestor/roster_validator│
│         fa/     analyzer/recommendation/real_time  │
├──────────────────────────────────────────────────┤
│ 数据层  db/     connection + repositories + schema  │
│         data_fetch/  projections/mlb_api/statcast  │
├──────────────────────────────────────────────────┤
│ 基础    config.py（统一配置）  utils/logger  plugins/ │
└──────────────────────────────────────────────────┘
```

分层规则：入口层只做参数收集与结果展示；业务层不直接发 HTTP（经 data_fetch）、不写裸 SQL（经仓储）；所有路径相对 PROJECT_ROOT 解析（打包后 = exe 所在目录，`utils/logger.py` 的 `sys.frozen` 检测）。

---

## 3. 核心算法

### 3.1 VORP（`core/scoring.py`）

**打者评分**：`score = Σ stat × weight`（权重来自 `league.scoring.hitters`，AVG 直接以小数参与）。投手同理，ERA/WHIP 权重为负。

**动态替代水平**（本项目的关键设计）：

```
drafted     = league_size × pos_slots                # 该位置联盟总需求
stream_share = stream_slots × pos_slots / total_slots # 机动席位按槽位分摊
fixed       = max(1, drafted − stream_share)          # 固定持有的球员数
q           = 1 − fixed / total_players               # 升序分位点（clip [0.10, 0.90]）
replacement = 该位置分数池的 q 分位数
VORP        = score − replacement
```

要点：
- 分位点取 `1 − fixed/total`（固定被选球员中的**最后一名**，即降序第 fixed 名）。曾实现为 `fixed/total`（方向颠倒，中游球员 VORP 符号翻转）——首轮审计修复。
- `stream_slots`（默认 5，可配置）表达"这些席位的球员本质是替代水平"的用户洞察。
- **SP/RP 分别计算**替代水平；主位置 UTIL 用全体打者池按打者总槽位的分位数（UTIL 池极小会被 clip 到个位数）。
- **多位置资格** `eligible_pos`（"2B,SS"）：取所有合格位置中替代水平最低者；**UTIL 不参与多位置比较**（曾因 UTIL 泄漏使 192/855 打者 VORP 虚高均值 +34——二轮审计修复）。

**风险评分**：z_score 法按同类型球员 vorp 标准差 ± 展开；historical_variance 法为 `vorp ± adj×|vorp|`（对称展开，负 VORP 方向也正确）；单行组回退 ±10%。floor 统一 clip ≥ 0。

### 3.2 SGP（`core/sgp.py`）

每个类别"能让你升几名"：

- 计数类：`stat / denominator`，分母按 `league_size/12` 线性缩放（12 队经验值基准）
- AVG：`(H+H̄)/(AB+AB̄) − .267`，团队基准 1768H/6617AB
- ERA：`(ER+475)×9/(IP+1192) − 3.59`，分母为负（低 ERA 为正贡献）
- WHIP：`(H+BB+1466)/(IP+1192) − 1.23`

**缺列反推**（CSV 管线无 AB/H/ER/K 时）：按定义精确换算 `ER=ERA×IP/9`、`K=K/9×IP/9`、`H+BB=WHIP×IP`、`H=AVG×AB`、`AB≈0.88×PA`；反推不出记 NaN（中性）——绝不 fillna(0) 当真实零产量（曾导致 ERA 分只随局数单调、方向倒置）。

**替代水平调整**：全池按 sgp_total 降序，第 `league_size×rounds` 名的 sgp 被减去（边缘球员归零）。

### 3.3 蒙特卡洛（`core/monte_carlo.py`）

**可用性估算**（解析式，非模拟）：

```
P(可用@target_pick) = 1 − 0.5 × (1 + tanh((target_pick − adp) / 10 / √2))
```

**多次模拟**：按 ADP 顺序 + tanh 噪声选人，统计被选率/平均顺位。numba njit 加速，不可用时纯 numpy 降级；支持取消检查。SGP 模式经 `_prepare_pool` 内部别名 `vorp=sgp_total`，输出列还原为 `sgp_total`。

### 3.4 选秀模拟（`core/draft.py`）

蛇形顺序（奇数轮 1→N、偶数轮 N→1）；选人综合：策略排序（balanced=均值 / conservative=floor / aggressive=upside；SGP 模式用 sgp_total）+ 稀缺位置 10% 加成 + **类别平衡 bonus**（仅用户队：阵容最弱类别按联盟典型总量归一化比较，bonus 用原始值 ×0.02）。

**价值股**：`total_pick − adp > 5`（球员滑落到你手里；曾实现方向相反）。

### 3.5 Sleeper（`core/sleeper.py`）

`bias = adp − expected_pick`（expected_pick = VORP 排名），bias 大 = 市场低估。Statcast 增强：显式 CSV 优先，否则逐球员 `search_player + StatcastFetcher`（带 JSON 缓存）。

### 3.6 FA 评分（`fa/`）

```
overall_value = position_adjusted×0.3 + trend×0.15 + statcast×0.25 + position_adjusted×0.3
final_score   = overall_value × (1 + need_factor×0.5) × risk_adjustment
```

- **position_adjusted** = base_score × 位置稀缺系数（C 1.3 / SS 1.2 / 2B 1.1 / 3B 1.05 / 1B 0.9 / OF 0.85 / RP 1.15）
- **statcast_score**：基准 50 的相对分，组件 `(值−联盟典型)×权重`；**缺失键中性跳过**（不当最差值）。注意投手 xera 是 Savant 聚合口径（面对打者 xwOBA×5.5 ≈ 1.8~2.2），非官方 xERA 量级
- **trend**：近 10 场 vs 赛季均值，基准 100
- **伤病**：单一 `INJURY_FACTORS` 表（mild .90 / moderate .75 / severe .55 / long_term .30）作用于 base_score；推荐侧再按**半权重**表达风险偏好（conservative ×1.5 / balanced ×1.0 / aggressive ×0.5 作用于惩罚幅度）
- **need_factor**：阵容缺口（0~1），位置经 `_normalize_slot` 归一化（CF/RF/LF→OF、DH→UTIL、P→SP）
- **is_mock**：真实数据不可用降级 mock 时标记，GUI 显示"（示例数据）"

---

## 4. 数据层

### 4.1 SQLite Schema（13 张业务表）

| 表 | 语义 | 写入模式 |
|----|------|---------|
| hitters / pitchers / player_positions | 预测原始 + 位置映射 | 每次导入整体替换 |
| hitters_merged / pitchers_merged | 多源加权融合 / 网络直写 | 整体替换 |
| fa_pool / user_roster / injury_reports / player_season_stats | FA 池 / 用户阵容 / 伤病 / 赛季统计 | 替换或增量 |
| adp | ADP 快照（fetched_at 驱动 TTL） | 整体替换 |
| rankings | 排名快照（method 区分 vorp/sgp） | 按 method 替换 |
| draft_logs / fa_recommendations | 会话记录（session_id 含毫秒时间戳） | 追加（同 session 幂等重写） |

连接管理：**每次操作新连接**（修复过单例连接跨进程不可见问题）、`busy_timeout=30s`、`PRAGMA foreign_keys=ON`。历史外键表通过 `_migrate_legacy_fk_tables` 一次性备份重建迁移（user_roster 曾因新 schema 仍含 FK 导致每次连接重建表——已修）。

### 4.2 存储策略：DB 唯一当前源 + CSV 备份

```
生成 rankings/draft_log/FA 推荐/ADP
  ├─ DB 写入（当前状态或会话）
  ├─ output/<名>.csv        「最近一份」（原子写：temp + os.replace）
  └─ output/history/<名>_<毫秒时间戳>.csv   永不覆盖的历史备份
```

读取优先级（以 ADP 为例，五级回退）：

```
内存 → DB（fetched_at 未过期）→ 根目录旧 adp.csv → output/adp.csv 最近一份 → 网络抓取 → mock
```

- ADP TTL 12 小时；CSV 有效且 DB 为空时自动回填（**保留 CSV 原龄**，不刷新租期）
- mock 数据**永不落盘/落库**（H3 原则）；时间戳统一本地时间（`_local_now`，SQLite CURRENT_TIMESTAMP 是 UTC 曾差 8 小时）
- `write_csv_atomic`：temp + `os.replace` 原子替换，防并发写坏回退源
- `history_path`：毫秒时间戳 + 进程内递增序号 + 磁盘存在性序号三重防碰撞

### 4.3 仓储模式（`db/repositories.py`）

每个聚合一个仓储类，持有外部传入的连接；事务由 `db_session()` 上下文统一 commit/rollback。`_insert_rows` 按全部行列集并集对齐（缺失列填 NULL——修复过按第一行建 INSERT 的 KeyError）。

---

## 5. 数据源与抓取（`data_fetch/`）

| 模块 | 源 | 说明 |
|------|----|------|
| projections.py | FantasyPros HTML | html.parser 零依赖解析；列映射对齐内部格式；`eligible_pos` 多位置提取；PA≈AB+BB |
| mlb_api.py | MLB Stats API | 球员搜索/统计/伤病（transactions 解析）/近 10 场趋势；网络失败 raise（与"无数据"区分）；JSON 缓存 6h |
| statcast.py | Baseball Savant CSV | 打者/投手聚合；mock 兜底带降级语义 |
| savant_leaderboard.py | Baseball Savant 排行榜 | 百分位/期望统计全联盟快照（CSV 端点，team= 参数），评分基准归一 + 运气指数，7 天缓存 |

抓取通用约束：urllib + 浏览器 UA、JSON/CSV 缓存（`data/cache/`，mtime TTL）、全部免费无 key、断网可降级。

---

## 6. GUI 架构（`gui/`）

**线程模型**：UI 线程只做渲染；后台任务经 `run_async` 进 daemon 线程，结果/错误/进度经 `queue` 回传；`_poll_queue` 在 UI 线程轮询分发。

关键设计（均有回归测试）：
- **轮询链永不死亡**：`after` 重排置于 finally，error 回调自身崩溃被捕获并弹窗
- **每任务独立取消信号**（线程 ident → Event 映射）：并发任务互不误伤；取消按钮作用于最近可取消任务
- **忙碌反馈**：任务期间 watch 光标 + 递归禁用全部按钮（取消按钮豁免），按 `_active_tasks` 计数收敛
- **Tk 变量只在 UI 线程读取**：worker 用闭包捕获的字符串值，int 转换留在工作线程走错误弹窗
- 配置页：Canvas 滚动 + 三列布局；滚轮 Enter/Leave 忽略 `NotifyInferior`

**错误中文化**（`gui/errors.py`）：`friendly_error` 按消息正则/异常类型映射中文说明，已含中文的消息透传，附原始详情。

---

## 7. CLI 与分发

**CLI**（12 子命令）：ingest / fetch-projections / rank / adp / draft / simulate / sleeper / validate / roster / fa / mlb / gui；`main()` 统一异常兜底（中文错误行）。

**双击入口**（GBK 编码的 .bat——cmd 用系统代码页解析批处理，UTF-8+chcp 组合会解析错乱）：

- `run_gui.bat` / `run_cli.bat`（14 项中文菜单，参数提示回车取默认）
- **便携运行时探测**：存在 `runtime\python.exe` 则用之（并设 TCL_LIBRARY/TK_LIBRARY），否则回落系统 Python

**两种分发**：

| | PyInstaller exe | 便携 runtime |
|---|---|---|
| 体量 | 849MB（onedir） | 160MB |
| 特性 | 纯 exe 双击 | 嵌入式 Python 3.7.9 + pip 依赖 + Anaconda 拼装的 tkinter |
| 改动生效 | 需重打包 | 即刻生效 |

便携 runtime 组装配方见 README「免安装便携模式」；`runtime/` 不入 git。

---

## 8. 配置系统（`config.py`）

- `get_config()`：懒加载单例 + DEFAULTS 深合并 + 校验，返回深拷贝
- `save_config_values()`：**按完整点分路径**逐行替换（`_index_config_line_paths` 缩进栈推断层级），保留注释；跨段同名 key（`league...R` vs `sgp...R`）严格隔离（曾相互覆盖——首轮审计实测复现修复）；未命中路径返回列表由 GUI 提示
- 赛季参数化：`data.season`（默认当前年）贯穿文件名/抓取年份；`file_patterns` 支持 `{season}` `{source}` 占位符
- 输出路径族：`output_path`（最近一份）/ `history_path`（时间戳备份）/ `find_output_file`（读取回退链）

---

## 9. 测试与 CI

**测试**：207 个（pytest），分层——数值回归（固定数据钉具体值，算法变更立即暴露）、DB 仓储语义、抓取解析（mock HTTP）、GUI 构造与线程模型、管道双写。

关键测试基建：
- `fresh_conn`：临时库连接；`isolated_db` / `isolated_history`：把业务模块内的 `db_session`/备份路径重定向到临时目录（防测试污染真实库——曾被污染过）
- GUI 测试 `_process_events` 驱动**真实** `_poll_queue`（CI 首跑发现手动分发回调会与轮询器竞争）

**CI**（`.github/workflows/ci.yml`）：push/PR 触发，Python 3.9 + 3.11 矩阵，ubuntu + xvfb 虚拟显示，只装核心依赖（可选依赖走降级路径）。

**日志**：`logs/YYYY-MM-DD.log`，RotatingFileHandler 10MB×5 + 30 天保留期清理（含轮转副本）。

---

## 10. 历史设计决策（ADR 摘要）

| 决策 | 背景 |
|------|------|
| 每次操作新 DB 连接 | 单例连接曾导致跨进程数据不可见 |
| mock 永不落盘/落库 | 离线 mock 曾污染真实缓存，联网后 TTL 内仍读 mock |
| 伤病双表合一 + 半权重 | 两套系数全额叠乘使 long_term 惩罚 ≈ ×0.045，球员从推荐消失 |
| xera 对齐聚合口径 | 评分按官方 xERA 量级基准导致联网投手恒饱和 100 |
| bat 一律 GBK | UTF-8+chcp 在 cmd 下解析错乱（run_cli 与 build 均踩坑） |
| 会话表用追加而非替换 | 支持多顺位模拟对比；session_id 含毫秒防同秒互删 |
| DB 优先于文件 | 统一入库前 CSV 同名覆盖丢历史；现 DB=当前态，CSV=备份 |

---

## 11. 已知限制与演进路线

- **P4a ESPN 联盟接入**：方案已定稿（`docs/PLAN_P4_LEAGUE_PLATFORM.md`），LeagueProvider 抽象预留 Yahoo（大陆网络封锁暂缓）
- F1 模拟战绩榜 / F2 GUI 表格化 / F3 Streaming 建议 / F4 交易评估 / F5 逐周对手 / F6 SGP 分母校准（见 TODO.md）
- SGP 分母为 12 队经验值，未按联盟历史校准
- risk model 的 z_score 假设同方差；numba 加速仅蒙特卡洛核心
