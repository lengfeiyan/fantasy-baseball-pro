"""ADP（Average Draft Position）数据获取。

**真实数据源**：[FantasyPros](https://www.fantasypros.com/mlb/adp/overall.php)
聚合 Yahoo / CBS / NFBC / ESPN 等平台的 ADP，约 600 名球员。

设计要点：
- 零额外依赖：用标准库 ``html.parser`` 解析表格，无需 lxml/bs4。
- 优雅降级：无网络、抓取失败、或未安装 requests 时，回退到内置 mock 数据，
  保证离线环境下工具仍可用（与旧版行为一致）。
- 本地缓存：抓取成功后写入 CSV，后续读取优先用缓存（可配置 TTL）。
"""

from __future__ import annotations

import csv
import os
import re
import time
from html.parser import HTMLParser
from typing import List, Optional

import pandas as pd

from ..config import get_config, resolve_path
from ..utils.logger import get_logger

logger = get_logger("adp")

FANTASYPROS_URL = "https://www.fantasypros.com/mlb/adp/overall.php?print=true"
DEFAULT_CACHE_TTL_HOURS = 12  # ADP 变动较频繁，默认 12 小时

# 请求超时（秒）
_REQUEST_TIMEOUT = 20

# 内置 mock ADP 数据（离线降级用，与旧版保持一致）
_MOCK_ADP = [
    {"name": "Ronald Acuña Jr.", "pos": "OF", "adp": 1.1},
    {"name": "Shohei Ohtani", "pos": "UTIL", "adp": 1.2},
    {"name": "Mookie Betts", "pos": "OF", "adp": 3.5},
    {"name": "Mike Trout", "pos": "OF", "adp": 4.2},
    {"name": "Juan Soto", "pos": "OF", "adp": 5.1},
    {"name": "Fernando Tatis Jr.", "pos": "SS", "adp": 6.3},
    {"name": "Aaron Judge", "pos": "OF", "adp": 7.2},
    {"name": "Corey Seager", "pos": "SS", "adp": 8.5},
    {"name": "Freddie Freeman", "pos": "1B", "adp": 9.1},
    {"name": "Rafael Devers", "pos": "3B", "adp": 10.2},
    {"name": "Bryce Harper", "pos": "OF", "adp": 11.5},
    {"name": "Manny Machado", "pos": "3B", "adp": 12.3},
    {"name": "Vladimir Guerrero Jr.", "pos": "1B", "adp": 13.1},
    {"name": "Francisco Lindor", "pos": "SS", "adp": 14.4},
    {"name": "Xander Bogaerts", "pos": "SS", "adp": 15.2},
    {"name": "Austin Riley", "pos": "3B", "adp": 16.5},
    {"name": "Kyle Tucker", "pos": "OF", "adp": 17.3},
    {"name": "Jorge Soler", "pos": "OF", "adp": 18.1},
    {"name": "José Ramírez", "pos": "3B", "adp": 19.4},
    {"name": "Ozzie Albies", "pos": "2B", "adp": 20.2},
    {"name": "Max Scherzer", "pos": "SP", "adp": 21.5},
    {"name": "Gerrit Cole", "pos": "SP", "adp": 22.3},
    {"name": "Jacob deGrom", "pos": "SP", "adp": 23.1},
    {"name": "Shane Bieber", "pos": "SP", "adp": 24.4},
    {"name": "Corbin Burnes", "pos": "SP", "adp": 25.2},
]

# 位置标准化映射：FantasyPros 可能出现的位置 → 统一简写
_POSITION_NORMALIZE = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "LF": "OF", "CF": "OF", "RF": "OF", "OF": "OF",
    "SP": "SP", "RP": "RP", "DH": "UTIL", "UTIL": "UTIL",
    # Ohtani 等二刀流球员在 FantasyPros 会被拆成 Batter/Pitcher 两条
    "Batter": "UTIL", "Pitcher": "SP",
}


class _ADPTableParser(HTMLParser):
    """轻量 HTML 表格解析器，提取 FantasyPros ADP 表的行。

    FantasyPros 表格列：Rank, Player (Team), Yahoo, CBS, RTS, NFBC, FT, ESPN, AVG
    我们只关心 Player 和 AVG（最后一列）。

    注意：FantasyPros 的 HTML 经常省略 ``</tr>`` 闭合标签，因此在遇到新的
    ``<tr>`` 或 ``</table>`` 时，也要把当前行收尾保存。
    """

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []

    def _finish_row(self):
        """保存当前行（若有内容）。"""
        if self.in_row and self.current_row:
            self.rows.append(self.current_row)
        self.current_row = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            # 新行开始 → 收尾上一行（兼容省略 </tr> 的情况）
            self._finish_row()
            self.in_row = True
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_row.append("")  # 占位，data 会追加

    def handle_endtag(self, tag):
        if tag == "table":
            self._finish_row()
            self.in_table = False
            self.in_row = False
        elif tag == "tr":
            self._finish_row()
            self.in_row = False
        elif tag in ("td", "th"):
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell and self.current_row:
            # 追加到最后一个 cell（处理单元格里嵌套 <a>/<small> 的多段文本）
            self.current_row[-1] += data.strip()


def _parse_player_cell(cell: str) -> tuple:
    r"""解析球员单元格 → (name, primary_pos, status)。

    FantasyPros 格式多样，例如：
      "Shohei Ohtani(LAD- SP,DH)"          （strip 后空格丢失）
      "Aaron Judge(NYY- LF,CF,RF,DH)IL60"  （带伤病状态）
      "Shohei Ohtani (Batter)(LAD- DH)"    （打者版，可能无球队-分隔）

    Returns:
        (name, primary_pos, status_or_none)
    """
    cell = cell.strip()
    # 分离名字和括号内容（最后一个括号为准，兼容名字里含括号的情况）
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*(.*)$", cell)
    if not m:
        return cell, "", None

    name = m.group(1).strip()
    paren = m.group(2).strip()
    trailing = m.group(3).strip()

    # 从括号内容提取位置：支持 "LAD - SP,DH" / "LAD- SP,DH" / "SP,DH" / "DH"
    pos = ""
    # 先去掉球队缩写（括号内容里第一个 " - " 或 "-" 前的部分，通常是球队）
    pos_part = paren
    # 球队缩写通常是 2-4 个大写字母，后跟 - 或空格
    team_match = re.match(r"^[A-Z]{2,4}\s*[-]\s*(.+)$", paren)
    if team_match:
        pos_part = team_match.group(1)
    elif " - " in paren:
        pos_part = paren.split(" - ", 1)[1]

    if pos_part:
        first_pos = pos_part.split(",")[0].strip()
        pos = _POSITION_NORMALIZE.get(first_pos, first_pos)

    status = trailing if trailing else None
    return name, pos, status


def _parse_adp_value(cell: str) -> Optional[float]:
    """把 ADP 单元格文本转为 float，失败返回 None。"""
    cell = cell.replace("&nbsp;", "").strip()
    if not cell or cell == "-":
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def parse_adp_html(html: str) -> pd.DataFrame:
    """解析 FantasyPros ADP 页面 HTML，返回 DataFrame(name, pos, adp)。

        Args:
            html: 页面 HTML 字符串。

        Raises:
            ValueError: HTML 中未找到有效 ADP 数据。
    """
    parser = _ADPTableParser()
    parser.feed(html)

    records = []
    for row in parser.rows:
        # 跳过表头行（含 "Rank"）和非数据行
        if len(row) < 3 or row[0].lower() == "rank":
            continue
        try:
            rank = int(row[0])
        except (ValueError, IndexError):
            continue

        player_cell = row[1]
        # AVG 在最后一列
        avg_cell = row[-1]
        adp = _parse_adp_value(avg_cell)
        if adp is None:
            continue

        name, pos, status = _parse_player_cell(player_cell)
        if not name:
            continue
        records.append({"rank": rank, "name": name, "pos": pos, "adp": adp})

    if not records:
        raise ValueError("HTML 中未解析出任何 ADP 数据")
    return pd.DataFrame(records)


def _fetch_html(url: str) -> str:
    """抓取 URL 内容。优先 requests，失败则用 urllib。

    Raises:
        ImportError: 无可用 HTTP 库。
        各种网络错误。
    """
    try:
        import requests  # type: ignore
        resp = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.text
    except ImportError:
        pass
    # 降级到标准库 urllib
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_real_adp(url: str = FANTASYPROS_URL) -> pd.DataFrame:
    """从 FantasyPros 抓取真实 ADP 数据。

    无网络时抛异常，调用方应捕获并降级到 mock。
    """
    logger.info("从 FantasyPros 抓取真实 ADP: %s", url)
    html = _fetch_html(url)
    df = parse_adp_html(html)
    logger.info("成功抓取 %d 名球员的真实 ADP", len(df))
    return df


class ADPCache:
    """ADP 缓存管理。

    优先级：内存缓存 → 本地 CSV 缓存（未过期）→ 在线抓取 → mock 降级。
    """

    def __init__(self, adp_file: Optional[str] = None, cache_ttl_hours: Optional[int] = None):
        cfg = get_config()
        self.adp_file = resolve_path(adp_file or cfg["draft_simulator"]["adp_file"])
        ttl = cache_ttl_hours if cache_ttl_hours is not None else DEFAULT_CACHE_TTL_HOURS
        self.cache_ttl = ttl * 3600
        self._df: Optional[pd.DataFrame] = None

    def fetch_adp(self, force: bool = False, allow_network: bool = True) -> pd.DataFrame:
        """获取 ADP 数据。

        Args:
            force: 强制重新抓取（忽略缓存）。
            allow_network: 是否允许联网。False 时只读缓存，无缓存则用 mock。
        """
        if self._df is not None and not force:
            return self._df

        # 1. 本地 CSV 缓存（未过期）
        if not force and self._cache_valid():
            try:
                self._df = pd.read_csv(self.adp_file)
                if not self._df.empty:
                    logger.info("从缓存加载 ADP: %s（%d 条）", self.adp_file, len(self._df))
                    return self._df
            except Exception as e:
                logger.warning("读取 ADP 缓存失败: %s", e)

        # 2. 在线抓取真实数据
        if allow_network:
            try:
                self._df = fetch_real_adp()
                self._save_cache(self._df)
                return self._df
            except Exception as e:
                logger.warning("抓取真实 ADP 失败，降级到 mock 数据: %s", e)

        # 3. mock 降级
        logger.info("使用内置 mock ADP 数据（%d 条）", len(_MOCK_ADP))
        self._df = pd.DataFrame(_MOCK_ADP)
        # mock 数据也写入缓存，便于离线下次直接读取
        if force or not os.path.exists(self.adp_file):
            self._save_cache(self._df)
        return self._df

    def _cache_valid(self) -> bool:
        if not os.path.exists(self.adp_file):
            return False
        age = time.time() - os.path.getmtime(self.adp_file)
        return age < self.cache_ttl

    def _save_cache(self, df: pd.DataFrame) -> None:
        try:
            os.makedirs(os.path.dirname(self.adp_file), exist_ok=True)
            df.to_csv(self.adp_file, index=False)
            logger.info("ADP 已缓存到: %s", self.adp_file)
        except OSError as e:
            logger.warning("写入 ADP 缓存失败: %s", e)

    def get_player_adp(self, name: str, allow_network: bool = True) -> Optional[float]:
        """查询单个球员的 ADP，未找到返回 None。

        Args:
            name: 球员姓名。
            allow_network: 是否允许联网（无缓存时）。测试中传 False 用 mock。
        """
        df = self.fetch_adp(allow_network=allow_network)
        # 精确匹配优先，其次忽略大小写
        hit = df[df["name"] == name]
        if hit.empty:
            name_lower = name.lower()
            hit = df[df["name"].str.lower() == name_lower]
        if hit.empty:
            return None
        return float(hit.iloc[0]["adp"])


def get_adp(force: bool = False, allow_network: bool = True) -> pd.DataFrame:
    """便捷函数：获取 ADP DataFrame。"""
    return ADPCache().fetch_adp(force=force, allow_network=allow_network)
