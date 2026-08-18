# P4 联盟平台接入方案（ESPN 先做，Yahoo 留接口）

> 状态：方案已定稿，待实施（ESPN 部分）
> 日期：2026-08-17
> 关联 TODO：TODO.md「⏸️ 已暂缓 → P4」

## 一、结论

**ESPN 部分可行。** ESPN Fantasy API（v3）已实测可用：`https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/2026` 返回正常 JSON（当前计分期 146）。公开联盟无需任何认证；私盟只需用户在浏览器里复制两个 cookie（SWID + espn_s2）填进配置。API 虽未官方文档化，但社区生态成熟（espn-api 库、ffscrapr、GitHub Gist "ESPN hidden API Docs"）。

**Yahoo 维持暂缓。** 当前网络被 Yahoo 官方公告页拦截（2026-08-17 已用 curl + 真实浏览器双重实测：`sports.yahoo.com` 与 `fantasysports.yahooapis.com` 均返回"2021 年 11 月 1 日起，用户将无法从中国大陆使用 Yahoo 的产品与服务"）。Yahoo 对接需要代理 + OAuth 2.0，本轮只定义接口不实现。

## 二、架构：统一 Provider 抽象

新建 `src/fantasy_baseball/data_fetch/league_api.py`：

```
LeagueProvider（抽象基类）
├── fetch_league_info()      -> 联盟名/球队数/赛季
├── fetch_teams()            -> [{team_id, name, owner}]
├── fetch_team_rosters()     -> 每队球员列表（标准球员字段）
├── fetch_free_agents(limit) -> FA 池（标准球员字段）
└── ESPNProvider / YahooProvider（桩：抛中文提示"需代理+OAuth，暂未实现"）
```

**标准球员字段**：`{platform_id, name, team, pos, eligible_pos, status}`。入库时 `player_id` 留空，由现有 H4 兜底（按姓名搜 MLB id，`fa/recommendation.py`）做数据增强——无需维护 ESPN→MLB id 映射表。

## 三、ESPNProvider 实现细节

- **端点**：`apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}`，views：`mRoster`（阵容）、`mTeam`（球队）、`mSettings`（联盟设置）
- **FA 池**：`.../players?scoringPeriodId={当前期}&view=players_wl` + `X-Fantasy-Filter` JSON 头过滤 `FREEAGENT/WAIVERS`，单次 limit 50，用 offset 分页抓取（默认累计 1000 人，可配置）
- **认证**：公开联盟不带 cookie；私盟从配置读 `swid`/`espn_s2` 加 Cookie 头，401/403 时抛中文错误提示"cookie 过期请重新粘贴或把联盟设为公开"
- **映射**：ESPN 槽位号 → 项目位置（0=C、1=1B、2=2B、3=3B、4=SS、5=OF、14=SP、15=RP…），多位置进 eligible_pos；proTeamId → 队名缩写（一次拉取缓存）
- **网络层**：复用现有模式（`data_fetch/mlb_api.py` 的 `_http_get_json`）——urllib + UA、JSON 缓存（data/cache，TTL 可配）、失败不崩（raise 带中文说明，GUI 经 friendly_error 显示）

## 四、配置扩展

`config.yaml` 新增顶层段（config.py DEFAULTS 同步）：

```yaml
league_platform:
  type: "none"        # none | espn | yahoo
  league_id: ""
  season: 2026        # 默认跟随 data.season
  swid: ""            # ESPN 私盟（公开联盟留空）
  espn_s2: ""         # ESPN 私盟
  team_name: ""       # 你的球队名（同步阵容用）
  fa_limit: 1000      # FA 池抓取上限
```

- GUI「配置设置」新增「联盟平台绑定」区：平台下拉框（none/espn/yahoo）+ 各输入框，走现有 `save_config_values`
- Yahoo 选中时保存但不生效，UI 提示"需代理网络"

## 五、业务接入

1. **FA 池同步**：`RealTimeData.update_fa_pool()` 改造——配置了 espn 时走 `ESPNProvider.fetch_free_agents()` → `FaRepository.replace_pool()`；未配置保持内置 mock。GUI「更新FA池(内置)」按钮文案改为「同步FA池（ESPN/内置）」
2. **阵容同步**：新增 `RealTimeData.sync_roster_from_platform()`——拉球队列表，按 `team_name` 匹配你的球队（未配置时 GUI 弹选择框，CLI 报错提示）；该队球员 → `RosterRepository.replace_all()`
3. **CLI**：`fa update-fa` 自动走平台；新增 `roster sync-espn`
4. GUI「阵容验证」加「从ESPN同步阵容」按钮

## 六、测试与文档

- 新增 `tests/test_espn.py`：用 monkeypatch `_http_get_json` 返回固定 fixture JSON，测 provider 解析（槽位映射/球队/FA 分页）、RealTimeData 平台同步入库、cookie 缺失提示
- USER_GUIDE.md 增加「联盟平台绑定」章节（含如何找 league_id 和复制 cookie 的步骤）
- TODO.md 更新 P4 状态：ESPN 部分完成、Yahoo 部分仍暂缓

## 七、风险与缓解

| 风险 | 缓解 |
|------|------|
| ESPN API 未文档化，可能变更（2024.4 就换过一次域名） | 单一 provider 模块隔离；解析失败抛中文错误而非崩溃，mock 兜底 |
| 私盟 cookie 过期 | 401/403 时给出明确指引 |
| 中国大陆网络对 ESPN 的连通性未验证 | 实施第一步先在用户机器上 curl 验证，不通则告知 |
| ESPN player id ≠ MLB id | player_id 留空，走现有姓名搜索增强链路 |

## 八、实施顺序

1. 用户机器 curl 验证 ESPN 连通性
2. `league_api.py`（抽象 + ESPNProvider）+ 测试
3. 配置段 + GUI 绑定区
4. RealTimeData 改造 + GUI/CLI 接入
5. 全套测试 + 文档同步 + 提交
