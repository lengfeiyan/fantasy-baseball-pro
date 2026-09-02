"""MLB Stats API 客户端。

数据源：``statsapi.mlb.com``（官方免费 API，无需 key）。

提供：
- 球员搜索（名字 → MLB player_id）
- 打者/投手赛季统计
- 伤病动态（从 transactions 解析）

所有方法带 JSON 缓存（避免重复请求），网络失败时返回 None 让上层降级。
依赖：标准库 urllib（零额外依赖）。
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from ..config import get_season, resolve_path
from ..utils.logger import get_logger

logger = get_logger("data_fetch.mlb_api")

BASE_URL = "https://statsapi.mlb.com/api/v1"
_REQUEST_TIMEOUT = 15
_CACHE_TTL_HOURS = 6  # 统计数据缓存 6 小时

# 伤病天数 → 严重度映射（与 FA analyzer 的 injury_factors 对齐）
_INJURY_DAYS_TO_SEVERITY = {
    "10": "mild",       # 0.85
    "15": "moderate",   # 0.65
    "60": "severe",     # 0.40
}

# sportId → 级别标签（新秀雷达级别归因；1=MLB，11=AAA，12=AA，13=High-A，
# 14=Single-A，16=新秀联盟。15（短季 A）联盟已不存在，teams 端点 404，不查）
_LEVEL_BY_SPORT = {
    1: "MLB", 11: "AAA", 12: "AA", 13: "A+", 14: "A", 16: "ROK",
}


def _http_get_json(url: str, timeout: int = _REQUEST_TIMEOUT) -> Optional[dict]:
    """GET 请求返回 JSON。失败返回 None。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning("请求失败 %s: %s", url[:80], e)
        return None


def _http_get_text(url: str, timeout: int = _REQUEST_TIMEOUT) -> Optional[str]:
    """GET 请求返回文本（用于 CSV）。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("请求失败 %s: %s", url[:80], e)
        return None


class MLBStatsClient:
    """MLB Stats API 客户端（带 JSON 缓存）。"""

    def __init__(self, cache_dir: Optional[str] = None, cache_ttl_hours: int = _CACHE_TTL_HOURS):
        self.cache_dir = resolve_path(cache_dir or "data/cache")
        self.cache_ttl = cache_ttl_hours * 3600
        os.makedirs(self.cache_dir, exist_ok=True)

    # -------------------------------------------------------------- 球员搜索
    def search_player(self, name: str) -> Optional[Dict[str, Any]]:
        """按名字搜索球员，返回第一个匹配项 {id, fullName, position, ...}。

        找不到返回 None。
        """
        # search 接口用 "Last,First" 或 "Last" 格式
        # 但直接传全名也能工作，取第一个结果
        cache_key = f"search_{name.replace(' ', '_').replace(',', '')}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        # 尝试多种格式
        for query in [name, self._to_last_first(name)]:
            url = f"{BASE_URL}/people/search?names={query.replace(' ', '%20')}"
            data = _http_get_json(url)
            if data and data.get("people"):
                person = data["people"][0]
                self._save_cache(cache_key, person)
                return person
        logger.info("未找到球员: %s", name)
        return None

    @staticmethod
    def _to_last_first(name: str) -> str:
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[-1]},{parts[0]}"
        return name

    # -------------------------------------------------------------- 打者统计
    def fetch_hitter_stats(self, mlb_id: int, season: int) -> Optional[Dict[str, Any]]:
        """获取打者赛季统计。字段对齐项目内部命名。"""
        cache_key = f"hitter_{mlb_id}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{BASE_URL}/people/{mlb_id}"
            f"?hydrate=stats(group=[hitting],type=[season],season={season})"
        )
        data = _http_get_json(url)
        if not data or not data.get("people"):
            return None

        person = data["people"][0]
        stats_list = person.get("stats", [])
        if not stats_list or not stats_list[0].get("splits"):
            return None
        raw = stats_list[0]["splits"][0].get("stat", {})

        # 映射到项目内部字段名（与 config scoring 一致）
        result = {
            "name": person.get("fullName", ""),
            "team": self._extract_team(person),
            "pos": person.get("primaryPosition", {}).get("abbreviation", ""),
            "stats": {
                "AVG": _safe_float(raw.get("avg")),
                "HR": _safe_int(raw.get("homeRuns")),
                "RBI": _safe_int(raw.get("rbi")),
                "R": _safe_int(raw.get("runs")),
                "SB": _safe_int(raw.get("stolenBases")),
                "OBP": _safe_float(raw.get("obp")),
                "SLG": _safe_float(raw.get("slg")),
                "OPS": _safe_float(raw.get("ops")),
                "PA": _safe_int(raw.get("plateAppearances")),
            },
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save_cache(cache_key, result)
        return result

    # -------------------------------------------------------------- 投手统计
    def fetch_pitcher_stats(self, mlb_id: int, season: int) -> Optional[Dict[str, Any]]:
        """获取投手赛季统计。K/9 从 K 和 IP 计算（API 的 strikeoutsPer9Inn 常为空）。"""
        cache_key = f"pitcher_{mlb_id}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{BASE_URL}/people/{mlb_id}"
            f"?hydrate=stats(group=[pitching],type=[season],season={season})"
        )
        data = _http_get_json(url)
        if not data or not data.get("people"):
            return None

        person = data["people"][0]
        stats_list = person.get("stats", [])
        if not stats_list or not stats_list[0].get("splits"):
            return None
        raw = stats_list[0]["splits"][0].get("stat", {})

        # K/9 和 BB/9 从原始字段计算（API 字段常为空）
        k9 = _calc_per9(raw.get("strikeOuts"), raw.get("inningsPitched"))
        bb9 = _calc_per9(raw.get("baseOnBalls"), raw.get("inningsPitched"))

        result = {
            "name": person.get("fullName", ""),
            "team": self._extract_team(person),
            "pos": person.get("primaryPosition", {}).get("abbreviation", ""),
            "stats": {
                "W": _safe_int(raw.get("wins")),
                "L": _safe_int(raw.get("losses")),
                "SV": _safe_int(raw.get("saves")),
                "HOLD": _safe_int(raw.get("holds")),
                "ERA": _safe_float(raw.get("era")),
                "WHIP": _safe_float(raw.get("whip")),
                "K_per_9": k9,
                "BB_per_9": bb9,
                "IP": _safe_float(raw.get("inningsPitched")),
            },
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save_cache(cache_key, result)
        return result

    # -------------------------------------------------------------- 通用统计
    def fetch_player_stats(self, mlb_id: int, season: int) -> Optional[Dict[str, Any]]:
        """根据球员位置自动取打者或投手统计。"""
        cache_key = f"player_{mlb_id}_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        # 先查位置
        url = f"{BASE_URL}/people/{mlb_id}"
        data = _http_get_json(url)
        if not data or not data.get("people"):
            return None
        pos = data["people"][0].get("primaryPosition", {}).get("abbreviation", "")

        if pos in ("P", "TWP"):  # TWP = 两刀流，按投手取
            result = self.fetch_pitcher_stats(mlb_id, season)
        else:
            result = self.fetch_hitter_stats(mlb_id, season)
        self._save_cache(cache_key, result)
        return result

    # -------------------------------------------------------------- 近期表现（趋势分用）
    def fetch_recent_performance(
        self, mlb_id: int, season: int, last_n_games: int = 10
    ) -> Optional[Dict[str, float]]:
        """拉取近 N 场比赛的聚合表现（基于逐场 gameLog）。

        用于趋势分计算：近 N 场表现对比赛季均值，判断上升/下降趋势。

        Returns:
            {avg, hr, rbi, runs, sb, ops(近似)} 或 None（无数据）。
        """
        cache_key = f"recent_{mlb_id}_{season}_{last_n_games}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        # 先查位置决定 group
        url_pos = f"{BASE_URL}/people/{mlb_id}"
        data = _http_get_json(url_pos)
        if not data or not data.get("people"):
            return None
        pos = data["people"][0].get("primaryPosition", {}).get("abbreviation", "")
        group = "pitching" if pos in ("P", "TWP", "SP", "RP") else "hitting"

        url = (
            f"{BASE_URL}/people/{mlb_id}"
            f"?hydrate=stats(group=[{group}],type=[gameLog],season={season})"
        )
        data = _http_get_json(url)
        if not data or not data.get("people"):
            return None
        stats = data["people"][0].get("stats", [])
        if not stats or not stats[0].get("splits"):
            return None

        games = stats[0]["splits"][-last_n_games:]
        if not games:
            return None

        if group == "hitting":
            result = _aggregate_recent_hitter(games)
        else:
            result = _aggregate_recent_pitcher(games)

        self._save_cache(cache_key, result)
        return result

    # -------------------------------------------------------------- 赛季 holds
    def fetch_season_holds(self, season: int) -> Dict[str, int]:
        """拉取某赛季全体投手的 holds（姓名 → 赛季总 holds）。

        背景：FantasyPros 预测页没有 HOLD 列（已实测确认），而 VORP 投手
        权重含 HOLD——本方法用 MLB Stats API 的「上赛季真实 holds」补源。
        比率/计数类预测缺列的处理原则一致：有精确数据就补精确数据。

        实现：遍历 30 支球队 roster + hydrate 上赛季投手统计。注：
        - ``/api/v1/stats?stats=season`` 端点带资格过滤（只返回 ~50 名
          合格先发），拿不到中继投手，故走 roster 路线；
        - 交易球员的 splits 按队拆分（如 Bednar 出现 3 段），按人求和；
        - 当前不在任何大名单 roster 的球员会缺失（对预测池影响极小）。

        结果整包缓存（历史静态数据，30 天 TTL 足够）。
        """
        cache_key = f"season_holds_{season}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        teams = _http_get_json(f"{BASE_URL}/teams?sportId=1&season={season}")
        if not teams or not teams.get("teams"):
            logger.warning("获取球队列表失败，holds 补源跳过")
            return {}

        holds: Dict[str, int] = {}
        n_teams = 0
        for team in teams["teams"]:
            team_id = team.get("id")
            if not team_id:
                continue
            url = (
                f"{BASE_URL}/teams/{team_id}/roster"
                f"?hydrate=person(stats(group=[pitching],type=[season],season={season}))"
            )
            data = _http_get_json(url, timeout=30)
            if not data or not data.get("roster"):
                continue
            n_teams += 1
            for entry in data["roster"]:
                stats_blocks = entry.get("person", {}).get("stats")
                if not stats_blocks:
                    continue
                splits = stats_blocks[0].get("splits", [])
                # hydrate 返回两类 split：无 team 字段的是赛季汇总，
                # 有 team 的是交易分队明细（两者数值相等）。实测曾把
                # 汇总+分队全加起来导致 holds 翻倍（Rogers 32→64）。
                player_holds = 0
                for split in splits:
                    h = _safe_int(split.get("stat", {}).get("holds"))
                    if not h:
                        continue
                    if split.get("team"):
                        player_holds += h
                if player_holds == 0 and splits:
                    # 没有分队明细（整个赛季未换队）：取汇总 split
                    for split in splits:
                        if not split.get("team"):
                            player_holds = _safe_int(
                                split.get("stat", {}).get("holds")
                            ) or 0
                            break
                if player_holds:
                    name = entry["person"].get("fullName", "").strip()
                    # 同一球员可能出现在多队 roster（休赛期换队），取最大值
                    holds[name] = max(holds.get(name, 0), player_holds)

        logger.info(
            "赛季 holds 补源完成：%d 队，holds 非零球员 %d 名（%d 赛季）",
            n_teams, len(holds), season,
        )
        self._save_cache(cache_key, holds)
        return holds

    # -------------------------------------------------------------- 伤病
    def fetch_injuries(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """从 transactions 抓取伤病动态。

        Args:
            start_date / end_date: "YYYY-MM-DD" 格式。

        Returns:
            伤病列表，每项含 player_id/name/team/injury_type/severity/status/start_date。
        """
        cache_key = f"injuries_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        url = (
            f"{BASE_URL}/transactions?sportId=1"
            f"&startDate={start_date}&endDate={end_date}"
        )
        data = _http_get_json(url, timeout=30)
        if not data:
            # 修复审计项：网络失败与"该时段无伤病"此前都返回 []，上层
            # real_time 的 RuntimeError 分支永远不可达，GUI 把断网当无伤病。
            raise RuntimeError(
                f"无法访问 MLB Stats API（伤病数据 {start_date}~{end_date}），"
                "请检查网络后重试"
            )

        txns = data.get("transactions", []) if isinstance(data, dict) else []
        injuries = []
        for t in txns:
            desc = t.get("description", "")
            if "injured list" not in desc.lower():
                continue
            parsed = _parse_injury_transaction(t)
            if parsed:
                injuries.append(parsed)

        self._save_cache(cache_key, injuries)
        logger.info("抓取到 %d 条伤病动态（%s ~ %s）", len(injuries), start_date, end_date)
        return injuries

    # -------------------------------------------------------------- 新秀雷达（F7）
    def fetch_people_current_teams(self, person_ids: List[int],
                                   season: Optional[int] = None) -> Dict[int, Dict[str, Any]]:
        """批量查询球员现属球队 id 与当季 MLB 出场数（新秀雷达级别归因）。

        ``hydrate=currentTeam,stats(...)`` 一次带回两样关键证据：
        - currentTeam：小联盟球员=附属球队 id；**40 人名单球员=母队 MLB 组织 id**
          （无法单凭它区分"已登板"与"在 40 人名单未升班"，须结合 MLB 出场数）
        - 当季 sportId=1 出场数：GP>0 才算真登板

        Returns:
            {person_id: {"team_id": int|None, "mlb_gp": int}}；网络失败返回 {}。
        """
        if not person_ids:
            return {}
        ids = sorted({int(i) for i in person_ids})
        season = season or get_season()
        # v2：值结构从 {id: team_id} 升级为 {id: {team_id, mlb_gp}}，换键避开旧缓存
        key = f"people_ct_v2_{season}_{hash(tuple(ids)) & 0xFFFFFFFF}"
        cached = self._load_cache(key)
        if cached is not None:
            return {int(k): v for k, v in cached.items()}
        result: Dict[int, Dict[str, Any]] = {}
        for i in range(0, len(ids), 100):  # 批量端点按 100 人分片
            chunk = ids[i:i + 100]
            url = (f"{BASE_URL}/people?personIds={','.join(map(str, chunk))}"
                   f"&hydrate=currentTeam,stats(group=[hitting,pitching],type=[season])")
            data = _http_get_json(url, timeout=45)
            if data is None:
                logger.warning("批量 currentTeam 查询失败（%d 人分片）", len(chunk))
                return {}
            for person in data.get("people") or []:
                team = person.get("currentTeam") or {}
                mlb_gp = 0
                for stat in person.get("stats") or []:
                    for split in stat.get("splits") or []:
                        if (split.get("sport") or {}).get("id") == 1:
                            mlb_gp += split.get("stat", {}).get("gamesPlayed", 0) or 0
                result[int(person["id"])] = {
                    "team_id": team.get("id"), "mlb_gp": int(mlb_gp),
                }
        self._save_cache(key, result)
        return result

    def fetch_milb_team_level_map(self, season: Optional[int] = None) -> Dict[int, str]:
        """小联盟/大联盟球队 id → 级别标签映射（new秀雷达级别归因用）。

        按 sportId 拉各级别球队列表整包缓存 30 天（球队格局赛季内不变，
        与 holds 同策略）。复杂联盟与新秀联盟统一归 ROK。
        """
        season = season or get_season()
        key = f"team_level_map_{season}"
        cached = self._load_cache(key)
        if cached is not None:
            return {int(k): v for k, v in cached.items()}
        mapping: Dict[int, str] = {}
        for sport_id, label in _LEVEL_BY_SPORT.items():
            data = _http_get_json(f"{BASE_URL}/teams?sportId={sport_id}&season={season}")
            if data is None:
                logger.warning("球队级别映射查询失败: sportId=%s", sport_id)
                continue
            for team in data.get("teams") or []:
                mapping[int(team["id"])] = label
        if mapping:
            self._save_cache(key, mapping)
        return mapping

    # -------------------------------------------------------------- 缓存
    def _cache_file(self, key: str) -> str:
        safe = re.sub(r"[^\w\-]", "_", key)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _load_cache(self, key: str) -> Optional[Any]:
        path = self._cache_file(key)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.cache_ttl:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cache(self, key: str, data: Any) -> None:
        try:
            with open(self._cache_file(key), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("写入缓存失败: %s", e)

    @staticmethod
    def _extract_team(person: dict) -> str:
        team = person.get("currentTeam", {})
        if isinstance(team, dict):
            return team.get("name", "") or team.get("abbreviation", "")
        return ""


# -------------------------------------------------------------- 辅助函数
def _safe_float(v) -> Optional[float]:
    """安全转 float（处理 MLB 的 "-"/"-.---" 缺失占位符，保留负号）。

    修复 L3：原实现 ``str(v).replace("-", "")`` 会把负数的负号一并剥掉
    （"-0.5" 变 0.5，导致 ERA 差值为负等场景全部算错）。
    """
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "-.---", "---", "nan", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _calc_per9(stat: Optional[int], ip: Optional[str]) -> Optional[float]:
    """计算每 9 局值（K/9、BB/9）。IP 格式如 "195.1"（.1=1/3 局）。"""
    if stat is None or not ip:
        return None
    try:
        # MLB IP 格式：整数部分 + .1/.2 表示 1/3、2/3 局
        ip_parts = str(ip).split(".")
        ip_float = float(ip_parts[0])
        if len(ip_parts) > 1 and ip_parts[1] == "1":
            ip_float += 1 / 3
        elif len(ip_parts) > 1 and ip_parts[1] == "2":
            ip_float += 2 / 3
        if ip_float == 0:
            return None
        return round(float(stat) * 9 / ip_float, 2)
    except (ValueError, ZeroDivisionError):
        return None


def _parse_injury_transaction(t: dict) -> Optional[Dict[str, Any]]:
    """解析伤病 transaction → 结构化记录。"""
    desc = t.get("description", "")
    person = t.get("person") or {}
    name = person.get("fullName", "")
    pid = person.get("id")
    if not name:
        return None

    # 解析球队名（句首到动词之前）。
    # 修复审计项：动词列表缺 activated/transferred——激活记录（39/110 实测）
    # 全部解析出空队名。
    team_match = re.match(
        r"^(.+?)\s+(?:placed|reinstated|activated|transferred|signed|optioned|recalled|selected|claimed|designated|released)\b",
        desc,
    )
    team = team_match.group(1).strip() if team_match else ""

    # 解析伤病天数 → severity。
    # 修复审计项：转会记录（"from the 10-day ... to the 60-day injured list"）
    # 旧实现取第一个匹配 = 转出名单天数，60 天转会被降级成 mild；
    # 现优先取 "to the N-day"（转入名单），无转入时回落首个匹配。
    days_match = re.search(r"to the (\d+)-day", desc) or re.search(r"(\d+)-day", desc)
    days = days_match.group(1) if days_match else None
    severity = _INJURY_DAYS_TO_SEVERITY.get(days or "", "mild")

    # season-ending 关键词 → long_term
    if "season-ending" in desc.lower() or "out for season" in desc.lower():
        severity = "long_term"

    # 解析伤病类型（"injured list. <type>." 中的 <type>）
    type_match = re.search(r"injured list[^.]*\.\s*(.+?)\.?\s*$", desc, re.I)
    injury_type = ""
    if type_match:
        # 去掉 "retroactive to..." 等修饰
        itype = type_match.group(1).strip().rstrip(".")
        # 截断 retroactive / effective 等附加信息
        itype = re.split(r"\s+(?:retroactive|effective|sideways)", itype, flags=re.I)[0].strip()
        injury_type = itype if itype else ""

    # 状态：复出 → recovered，否则 IL。
    # 修复审计项：MLB 实际用 "activated X from the N-day injured list" 表达
    # 复出（实测 110 条 IL 记录中 "reinstated" 出现 0 次），旧实现只认
    # reinstated → 伤病惩罚永不解除，刚复出的健康球员持续按重伤扣分。
    lower = desc.lower()
    status = "recovered" if ("reinstated" in lower or "activated" in lower) else "IL"

    return {
        "player_id": pid,
        "name": name,
        "team": team,
        "injury_type": injury_type,
        "severity": severity,
        "status": status,
        "start_date": t.get("effectiveDate") or t.get("date", ""),
        "expected_return": "",
    }


# -------------------------------------------------------------- 近期表现聚合
def _aggregate_recent_hitter(games: list) -> Dict[str, float]:
    """聚合近 N 场逐场打者数据 → 每场均值的核心指标。"""
    n = len(games)
    if n == 0:
        return {}
    total_ab = sum(_safe_int(g["stat"].get("atBats")) or 0 for g in games)
    total_h = sum(_safe_int(g["stat"].get("hits")) or 0 for g in games)
    total_hr = sum(_safe_int(g["stat"].get("homeRuns")) or 0 for g in games)
    total_rbi = sum(_safe_int(g["stat"].get("rbi")) or 0 for g in games)
    total_r = sum(_safe_int(g["stat"].get("runs")) or 0 for g in games)
    total_sb = sum(_safe_int(g["stat"].get("stolenBases")) or 0 for g in games)
    total_bb = sum(_safe_int(g["stat"].get("baseOnBalls")) or 0 for g in games)
    total_2b = sum(_safe_int(g["stat"].get("doubles")) or 0 for g in games)
    total_3b = sum(_safe_int(g["stat"].get("triples")) or 0 for g in games)

    # 单场均值（便于和赛季"每场产出"对比）
    avg = total_h / total_ab if total_ab > 0 else 0.0
    return {
        "games": n,
        "avg": round(avg, 3),
        "hr_per_game": round(total_hr / n, 2),
        "rbi_per_game": round(total_rbi / n, 2),
        "r_per_game": round(total_r / n, 2),
        "sb_per_game": round(total_sb / n, 2),
        # OPS 近似 = AVG + 长打率；长打率用 (H+2B+2*3B+3*HR)/AB
        "ops_approx": round(
            avg + ((total_h + total_2b + 2 * total_3b + 3 * total_hr) / total_ab if total_ab > 0 else 0),
            3,
        ),
    }


def _aggregate_recent_pitcher(games: list) -> Dict[str, float]:
    """聚合近 N 场逐场投手数据 → 每场均值。"""
    n = len(games)
    if n == 0:
        return {}
    total_er = sum(_safe_int(g["stat"].get("earnedRuns")) or 0 for g in games)
    total_ip = 0.0
    for g in games:
        ip_str = g["stat"].get("inningsPitched", "0")
        ip_parts = str(ip_str).split(".")
        ip_val = float(ip_parts[0])
        if len(ip_parts) > 1 and ip_parts[1] == "1":
            ip_val += 1 / 3
        elif len(ip_parts) > 1 and ip_parts[1] == "2":
            ip_val += 2 / 3
        total_ip += ip_val
    total_k = sum(_safe_int(g["stat"].get("strikeOuts")) or 0 for g in games)
    total_bb = sum(_safe_int(g["stat"].get("baseOnBalls")) or 0 for g in games)
    total_h = sum(_safe_int(g["stat"].get("hits")) or 0 for g in games)

    return {
        "games": n,
        "era_recent": round(total_er / total_ip * 9 if total_ip > 0 else 0, 2),
        "k_per_game": round(total_k / n, 2),
        "bb_per_game": round(total_bb / n, 2),
        "whip_recent": round((total_h + total_bb) / total_ip if total_ip > 0 else 0, 2),
        "ip_total": round(total_ip, 1),
    }
