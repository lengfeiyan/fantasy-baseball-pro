"""MLB Pipeline 天赋榜快照（F7 新秀雷达数据源）。

端点考古结论（2026-09 实测）：
- Pipeline 榜单无官方 REST API。statsapi 的 ``/draft/prospects/{year}`` 是
  业余选秀名单（~2400 人），与 Pipeline Top100 榜不是一回事；社区确认无榜单端点。
- ``https://www.mlb.com/prospects/stats/top-prospects`` 页面为客户端渲染，但
  HTML 内嵌完整榜单数据：``var data = [ {...}, ... ]``（纯 JSON 数组）。
  每条含 rank / name / playerId（MLBAM id，可直接对接 Savant/Stats API）/
  age / position / team / teamId / slug / sportAbbrev（本赛季打过的级别标记，
  如 "AA"、"ALL (2)"）/ battingStats|pitchingStats（当季计数统计）/ avg|era。
- 页面无 ETA / 级别显式字段，「接近大联盟程度」需由 sportAbbrev + age 推导
  （见 core/rookies.py 的接近度启发式）。

设计要点：
- 榜单周级更新即可用于选秀准备，整包缓存默认 7 天（force 可强刷），
  缓存读写复用 MLBStatsClient 的既有机制（同一 data/cache 目录体系）
- HTML 提取失败返回 None（调用方决定降级路径），不抛网络异常中断链路
- 姓名规范化与 Savant/FantasyPros 对齐（"First Last"），便于跨源匹配
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..config import get_season
from ..utils.logger import get_logger
from .mlb_api import MLBStatsClient

logger = get_logger("data_fetch.pipeline")

TOP_PROSPECTS_URL = "https://www.mlb.com/prospects/stats/top-prospects"
_DEFAULT_TTL_HOURS = 7 * 24  # 榜单整包缓存 7 天（与 Savant 排行榜同策略）

# 抓取目标域名白名单：榜单页面只来自 MLB 官方站（修复审计高危：SSRF——
# 请求目标固定白名单，重定向逐跳校验，杜绝指向内网/元数据地址）
_ALLOWED_HOSTS = {"www.mlb.com"}

# sportAbbrev 中的级别标记（"ALL (n)" 表示一季打了 n 个级别，取其中最高级）
_LEVEL_TOKENS = ("MLB", "AAA", "AA", "A+", "A", "ROK")


def _validate_url(url: str) -> str:
    """校验抓取目标：必须 https 且域名在白名单内，否则拒绝。"""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"非白名单抓取目标被拒绝: {url!r}")
    return url


def extract_data_var(html: str) -> Optional[List[Dict[str, Any]]]:
    """从页面 HTML 提取内嵌的 ``var data = [...]`` 榜单数组。

    方括号配平而非正则截断——数组元素内含嵌套对象与字符串括号。
    找不到数据块或 JSON 解析失败返回 None（页面结构变更时上层降级）。
    """
    marker = html.find("var data =")
    if marker < 0:
        logger.debug("页面未找到 var data 数据块")
        return None
    arr_start = html.find("[", marker)
    if arr_start < 0:
        logger.debug("var data 后未找到数组起始括号")
        return None
    depth = 0
    end = None
    for i in range(arr_start, len(html)):
        ch = html[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        logger.debug("var data 数据块未闭合")
        return None
    try:
        data = json.loads(html[arr_start: end])
    except (ValueError, TypeError) as e:
        logger.debug("var data JSON 解析失败: %s", e)
        return None
    return data if isinstance(data, list) and data else None


def highest_level(sport_abbrev: str) -> str:
    """从 sportAbbrev 标记提取本赛季最高级别。

    "ALL (n)" 表示一季多级，无法得知具体哪几级，保守返回 "MULTI"；
    其余按 _LEVEL_TOKENS 顺序取最靠前的（MLB > AAA > AA > A+ > A > ROK）。
    """
    raw = str(sport_abbrev or "").strip()
    if not raw:
        return ""
    if raw.startswith("ALL"):
        return "MULTI"
    for token in _LEVEL_TOKENS:
        if token in raw:
            return token
    return raw


def normalize_prospect(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把 Pipeline 原始条目规整为雷达统一字段。"""
    # Pipeline 打者/投手统计分别挂在 battingStats / pitchingStats，统一挂 season_stats
    stats = raw.get("battingStats") or raw.get("pitchingStats") or {}
    return {
        "rank": raw.get("rank"),
        "name": " ".join(str(raw.get("name") or "").split()),
        "mlb_id": raw.get("playerId"),
        "age": raw.get("age"),
        "position": raw.get("position"),
        "team": raw.get("team"),
        "team_id": raw.get("teamId"),
        "levels": raw.get("sportAbbrev", ""),
        "top_level": highest_level(raw.get("sportAbbrev", "")),
        "avg": raw.get("avg"),
        "era": raw.get("era"),
        "season_stats": stats,
    }


def _fetch_html(url: str, timeout: int = 30) -> str:
    """抓取页面 HTML（域名白名单校验）。

    优先 requests，ImportError 时降级 urllib（与 adp.py 同策略）。
    requests 侧禁自动重定向、手动逐跳校验，防重定向绕过白名单。
    """
    _validate_url(url)
    try:
        import requests  # type: ignore
        from urllib.parse import urljoin
        current = url
        for _ in range(3):  # 手动跟随重定向，每一跳补全相对地址后都过白名单
            resp = requests.get(
                current,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                allow_redirects=False,
            )
            if resp.is_redirect or resp.is_permanent_redirect:
                nxt = resp.headers.get("Location", "")
                if not nxt:
                    break
                current = _validate_url(urljoin(current, nxt))
                continue
            resp.raise_for_status()
            return resp.text
        logger.warning("重定向次数超限或目标非法: %s", url)
        return ""
    except ImportError:
        pass
    import urllib.request

    class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
        """重定向逐跳过白名单（修复审计高危：SSRF 重定向绕过）。"""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            try:
                _validate_url(str(newurl))
            except ValueError:
                return None
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_PinnedRedirectHandler)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


class PipelineFetcher:
    """MLB Pipeline Top 榜单抓取与缓存。

    缓存读写直接复用 MLBStatsClient 的 JSON 缓存（TTL/目录策略一致，
    本模块不再自行拼装存储路径）。
    """

    def __init__(self, cache_dir: Optional[str] = None,
                 cache_ttl_hours: int = _DEFAULT_TTL_HOURS):
        self._store = MLBStatsClient(cache_dir=cache_dir,
                                     cache_ttl_hours=cache_ttl_hours)

    # -------------------------------------------------------------- 公开 API
    def fetch_top_prospects(self, season: Optional[int] = None,
                            force: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Top 天赋榜整包快照（页面 URL 固定为 TOP_PROSPECTS_URL，白名单内）。

        Returns:
            规整后的 prospect 字典列表（按 rank 排序）；网络失败/页面变更返回 None。
        """
        season = season or get_season()
        cache_key = f"pipeline_top_{season}"
        if not force:
            cached = self._store._load_cache(cache_key)
            if cached is not None:
                logger.info("Pipeline 榜单命中缓存（%d 人）", len(cached))
                return cached
        try:
            html = _fetch_html(TOP_PROSPECTS_URL)
        except Exception as e:
            logger.warning("Pipeline 页面抓取失败: %s", e)
            return None
        raw = extract_data_var(html)
        if raw is None:
            logger.warning("Pipeline 页面未提取到榜单数据（页面结构可能已变更）")
            return None
        prospects = sorted(
            (normalize_prospect(item) for item in raw),
            key=lambda p: (p["rank"] is None, p["rank"] or 0),
        )
        logger.info("Pipeline 榜单解析成功：%d 名 prospect", len(prospects))
        self._store._save_cache(cache_key, prospects)
        return prospects
