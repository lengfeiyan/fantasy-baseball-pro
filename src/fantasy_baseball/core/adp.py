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

from ..config import get_config, history_path, output_path, resolve_path
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

    优先级：内存 → 数据库快照（未过期）→ 本地 CSV（旧版回退，未过期）
    → 在线抓取（写库 + 时间戳备份）→ mock 降级（永不落盘/落库）。
    """

    def __init__(
        self,
        adp_file: Optional[str] = None,
        cache_ttl_hours: Optional[int] = None,
        use_db: bool = True,
    ):
        cfg = get_config()
        self.adp_file = resolve_path(adp_file or cfg["draft_simulator"]["adp_file"])
        ttl = cache_ttl_hours if cache_ttl_hours is not None else DEFAULT_CACHE_TTL_HOURS
        self.cache_ttl = ttl * 3600
        # DB 是默认管线的存储；显式指定 adp_file（测试/隔离场景）时自动关闭，
        # 避免临时 CSV 与真实库互相污染
        self.use_db = use_db and adp_file is None
        self._df: Optional[pd.DataFrame] = None
        # 本次数据的来源（供上层给出准确提示）：
        # network / db / csv_legacy / csv_latest / mock
        self.last_source = ""

    def fetch_adp(self, force: bool = False, allow_network: bool = True) -> pd.DataFrame:
        """获取 ADP 数据。

        Args:
            force: 强制重新抓取（忽略缓存）。
            allow_network: 是否允许联网。False 时只读缓存，无缓存则用 mock。
        """
        if self._df is not None and not force:
            return self._df

        # 1. 数据库快照（未过期）
        if not force and self.use_db:
            df = self._load_from_db()
            if df is not None and not df.empty:
                logger.info("从数据库加载 ADP（%d 条）", len(df))
                self.last_source = "db"
                self._df = df
                return self._df

        # 2. 本地 CSV 回退（根目录旧版文件，未过期）
        if not force and self._cache_valid():
            try:
                self._df = pd.read_csv(self.adp_file)
                if not self._df.empty:
                    logger.info("从缓存加载 ADP: %s（%d 条）", self.adp_file, len(self._df))
                    self.last_source = "csv_legacy"
                    self._backfill_db_from_csv(self._df)
                    return self._df
            except Exception as e:
                logger.warning("读取 ADP 缓存失败: %s", e)

        # 2b. 「最近一份」CSV 回退（output/adp.csv，本管道写入）。
        # 审计修复：此前 TTL 过期 + 断网时直接落到 25 条 mock，
        # 磁盘上 12 小时前的真实数据备份全程不被考虑。
        if not force and self.use_db:
            latest = output_path("adp.csv")
            if self._path_fresh(latest):
                try:
                    self._df = pd.read_csv(latest)
                    if not self._df.empty:
                        logger.info("从最近一份 CSV 加载 ADP: %s（%d 条）", latest, len(self._df))
                        self.last_source = "csv_latest"
                        self._backfill_db_from_csv(self._df)
                        return self._df
                except Exception as e:
                    logger.warning("读取最近一份 ADP CSV 失败: %s", e)

        # 3. 在线抓取真实数据 → 写库 + 双 CSV
        if allow_network:
            try:
                self._df = fetch_real_adp()
                self.last_source = "network"
                self._save_all(self._df)
                return self._df
            except Exception as e:
                logger.warning("抓取真实 ADP 失败，降级到 mock 数据: %s", e)

        # 4. mock 降级
        logger.info("使用内置 mock ADP 数据（%d 条）", len(_MOCK_ADP))
        self.last_source = "mock"
        self._df = pd.DataFrame(_MOCK_ADP)
        # 修复 H3：mock 数据**永不写盘/落库**（只驻留内存）。
        # 避免首次离线运行写入 mock 后，恢复联网的 12 小时 TTL 内仍读到 mock，
        # 也避免 force 刷新时用 mock 覆盖已有真实数据。
        return self._df

    # -------------------------------------------------------------- DB 存取
    def _load_from_db(self) -> Optional[pd.DataFrame]:
        """从数据库读未过期的 ADP 快照；无数据/过期/出错返回 None。"""
        try:
            from ..db import AdpRepository, db_session

            with db_session() as conn:
                repo = AdpRepository(conn)
                ts = repo.latest_fetch_time()
                if ts is None or self._age_seconds(ts) >= self.cache_ttl:
                    return None
                df = repo.get_all()
        except Exception as e:
            logger.warning("从数据库读取 ADP 失败: %s", e)
            return None
        keep = [c for c in ("name", "team", "pos", "adp") if c in df.columns]
        return df[keep]

    @staticmethod
    def _age_seconds(ts: str) -> float:
        """时间戳距今的秒数（仓储写入的是本地时间，按本地时区解析）；
        解析失败视为已过期。"""
        from datetime import datetime as _dt

        try:
            st = _dt.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
            return time.time() - time.mktime(st.timetuple())
        except (ValueError, TypeError, OverflowError):
            return float("inf")

    def _save_all(self, df: pd.DataFrame) -> None:
        """抓取成功后的持久化：DB（当前状态）+ 最近一份 CSV + 时间戳备份。

        审计修复：此前漏写「最近一份」（output/adp.csv），断网 + TTL 过期
        时 CSV 回退层只能读到旧版根目录文件，历史备份无读取端。
        """
        if self.use_db:
            try:
                from ..db import AdpRepository, db_session

                rows = df.to_dict("records")
                with db_session() as conn:
                    AdpRepository(conn).replace_all(rows)
                logger.info("ADP 已写入数据库（%d 条）", len(df))
            except Exception as e:
                logger.warning("ADP 写入数据库失败: %s", e)
        try:
            # 最近一份（同名覆盖，作为断网回退源）
            latest = output_path("adp.csv")
            df.to_csv(latest, index=False)
            # 时间戳历史备份（永不覆盖）
            backup = history_path("adp.csv")
            df.to_csv(backup, index=False)
            logger.info("ADP CSV 已保存：最近一份 %s；历史备份 %s", latest, backup)
        except OSError as e:
            logger.warning("写入 ADP 备份失败: %s", e)

    def _backfill_db_from_csv(self, df: pd.DataFrame) -> None:
        """DB 为空且读到有效 CSV 时，把 CSV 数据回填入库（一次性迁移）。

        让数据库尽快成为权威源；已有 DB 数据时不动作（不覆盖新状态）。
        """
        if not self.use_db:
            return
        try:
            from ..db import AdpRepository, db_session

            with db_session() as conn:
                repo = AdpRepository(conn)
                if repo.count() > 0:
                    return
                repo.replace_all(df.to_dict("records"))
            logger.info("已从 CSV 回填 ADP 到数据库（%d 条）", len(df))
        except Exception as e:
            logger.debug("ADP 回填数据库失败（忽略）: %s", e)

    def _path_fresh(self, path: str) -> bool:
        """文件存在且 mtime 在 TTL 内。"""
        if not os.path.exists(path):
            return False
        return time.time() - os.path.getmtime(path) < self.cache_ttl

    def _cache_valid(self) -> bool:
        return self._path_fresh(self.adp_file)

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
