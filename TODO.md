# 待办事项（TODO）

> 最后更新：2026-08-14
> 当前版本：2026.1.0 | 测试：135 passed | 已打包 Windows exe

---

## 🟡 评分算法改进（尚未实现）

暂无 — 核心算法改进已全部完成。

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
