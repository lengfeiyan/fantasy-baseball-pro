# 待办事项（TODO）

## P4：联盟平台 API 对接（暂缓）

**状态**：暂缓 — Yahoo 需要特殊网络条件才能访问，后续具备条件时再做。

**目标**：对接 ESPN / Yahoo / Sleeper 联盟 API，实现全自动 FA 池 + 用户阵容同步，彻底取代手动 CSV 导入。

### 背景
当前 FA 池和用户阵容已支持 CSV 手动导入（P2 + P3 已完成），但要获得"自己联盟里谁没被选"的真实 FA 池，需要对接联盟平台。每个平台的 FA 池因联盟而异，没有统一公开数据源。

### 需要做的事
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

### 实施方案（待定）
- 新建 `data_fetch/league_api.py`，按平台分别实现
- GUI 加"绑定联盟"配置（输入联盟 ID + 平台）
- 定期同步 FA 池 + 用户阵容到数据库

### 依赖
- ESPN：`espn-api` 或自实现
- Yahoo：OAuth2 流程，需用户注册 Yahoo 应用
- 网络：Yahoo 可能需要代理/VPN

### 优先级
低 — 手动 CSV 导入已满足基本需求，全自动同步是锦上添花。
