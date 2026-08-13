"""FantasyPros 预测数据抓取。

数据源：``fantasypros.com/mlb/projections/``（免费、无需 key）。
聚合 Steamer / ZiPS / THE BAT X / ATC 等多系统。

FanGraphs 自身 2026 起全面封禁非浏览器请求（403），FantasyPros 是可用的
替代源，且数据更全（聚合多系统）。返回的 DataFrame 列名与 ingestor 期望的
CSV 格式对齐，可直接入库。

打者列：name, team, pos, AB, R, HR, RBI, SB, AVG, OBP, SLG, OPS, PA(近似)
投手列：name, team, pos, IP, K_per_9, W, L, SV, ERA, WHIP, BB_per_9
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from ..core.adp import _ADPTableParser, _fetch_html, _parse_player_cell
from ..utils.logger import get_logger

logger = get_logger("data_fetch.projections")

HITTERS_URL = "https://www.fantasypros.com/mlb/projections/hitters.php?season={season}&scoring=standard"
PITCHERS_URL = "https://www.fantasypros.com/mlb/projections/pitchers.php?season={season}"

# FantasyPros 打者列 → 内部列名
_HITTER_COL_MAP = {
    "Player": "_player",
    "AB": "AB", "R": "R", "HR": "HR", "RBI": "RBI", "SB": "SB",
    "AVG": "AVG", "OBP": "OBP", "H": "H", "2B": "2B", "3B": "3B",
    "BB": "BB", "SO": "SO", "SLG": "SLG", "OPS": "OPS",
}

# FantasyPros 投手列 → 内部列名
_PITCHER_COL_MAP = {
    "Player": "_player",
    "IP": "IP", "K": "K", "W": "W", "SV": "SV",
    "ERA": "ERA", "WHIP": "WHIP", "ER": "ER", "H": "H",
    "BB": "BB", "HR": "HR", "G": "G", "GS": "GS", "L": "L",
}


def fetch_projections(
    player_type: str, season: int = 2026
) -> pd.DataFrame:
    """从 FantasyPros 抓取预测数据。

    Args:
        player_type: "hitters" 或 "pitchers"。
        season: 赛季年份。

    Returns:
        DataFrame，列名对齐项目内部格式（与 ingestor 的 CSV 期望一致）。
        打者含 name/team/pos/R/HR/RBI/SB/AVG/OBP/SLG/OPS/PA；
        投手含 name/team/pos/W/L/SV/ERA/WHIP/K_per_9/BB_per_9/IP。

    Raises:
        ValueError: player_type 非法或解析失败。
    """
    if player_type == "hitters":
        return _fetch_hitters(season)
    elif player_type == "pitchers":
        return _fetch_pitchers(season)
    raise ValueError(f"player_type 必须是 hitters/pitchers，得到 {player_type}")


def _fetch_hitters(season: int) -> pd.DataFrame:
    """抓取打者预测。"""
    url = HITTERS_URL.format(season=season)
    logger.info("从 FantasyPros 抓取打者预测: %s", url)
    try:
        html = _fetch_html(url)
    except Exception as e:
        raise ValueError(f"无法获取打者预测页面（season={season}）: {e}") from e

    df = _parse_table(html, _HITTER_COL_MAP)
    if df.empty:
        raise ValueError("打者预测页面未解析出数据")

    # PA 近似 = AB + BB（FantasyPros 不直接给 PA）
    df["PA"] = _safe_num(df.get("AB")) + _safe_num(df.get("BB"))

    logger.info("抓取到 %d 名打者预测", len(df))
    return df


def _fetch_pitchers(season: int) -> pd.DataFrame:
    """抓取投手预测。"""
    url = PITCHERS_URL.format(season=season)
    logger.info("从 FantasyPros 抓取投手预测: %s", url)
    try:
        html = _fetch_html(url)
    except Exception as e:
        raise ValueError(f"无法获取投手预测页面（season={season}）: {e}") from e

    df = _parse_table(html, _PITCHER_COL_MAP)
    if df.empty:
        raise ValueError("投手预测页面未解析出数据")

    # K/9、BB/9 从 K/BB 和 IP 计算
    from .mlb_api import _calc_per9
    df["K_per_9"] = [
        _calc_per9(k, ip) for k, ip in zip(df.get("K", []), df.get("IP", []))
    ]
    df["BB_per_9"] = [
        _calc_per9(bb, ip) for bb, ip in zip(df.get("BB", []), df.get("IP", []))
    ]

    logger.info("抓取到 %d 名投手预测", len(df))
    return df


def _parse_table(html: str, col_map: dict) -> pd.DataFrame:
    """解析 FantasyPros 表格 HTML，返回标准化 DataFrame。

    复用 ADP 的 _ADPTableParser（处理省略 </tr>、嵌套标签）。
    """
    parser = _ADPTableParser()
    parser.feed(html)

    # 第一个有数据的表（跳过表头行）
    headers: List[str] = []
    data_rows: List[List[str]] = []
    for row in parser.rows:
        if not row:
            continue
        # 表头行（含 "Player"）
        if not headers and "Player" in [c.strip() for c in row]:
            headers = [c.strip() for c in row]
            continue
        if not headers:
            continue
        # 数据行：长度应与表头接近（可能有额外的 Rost% 等列）
        if len(row) >= len(headers):
            data_rows.append(row[:len(headers)])

    if not headers or not data_rows:
        return pd.DataFrame()

    raw_df = pd.DataFrame(data_rows, columns=headers)

    # 解析 Player 列 → name/team/pos
    players = raw_df["Player"].apply(lambda x: _parse_player_cell(x or ""))
    raw_df["name"] = [p[0] for p in players]
    raw_df["team"] = [p[1] for p in players]  # _parse_player_cell 返回 (name, pos, status)
    # 注意：_parse_player_cell 返回 (name, pos, status)，team 在括号里未单独提取
    # 这里 pos 取第二个返回值
    raw_df["pos"] = [p[1] for p in players]

    # 重新从 Player 列提取 team（括号里的球队缩写）
    raw_df["team"] = raw_df["Player"].apply(_extract_team)

    # 列名映射 + 数值转换
    result = pd.DataFrame()
    result["name"] = raw_df["name"]
    result["team"] = raw_df["team"]
    result["pos"] = raw_df["pos"]
    for fp_col, internal_col in col_map.items():
        if fp_col == "Player":
            continue
        if fp_col in raw_df.columns:
            result[internal_col] = raw_df[fp_col].apply(_to_float)

    return result


def _extract_team(player_cell: str) -> str:
    """从 "Shohei Ohtani (LAD - SP,DH)" 提取球队 "LAD"。"""
    import re
    m = re.search(r"\(([A-Z]{2,4})\s*[-]", player_cell or "")
    return m.group(1) if m else ""


def _to_float(v):
    """安全转 float（处理 '.282'、'' 等）。"""
    if v is None or v == "" or v == "-":
        return None
    s = str(v).strip().replace("&nbsp;", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_num(series) -> pd.Series:
    """把 series 转为数值，None 填 0。"""
    if series is None:
        return pd.Series(0, index=range(0))
    return pd.to_numeric(series, errors="coerce").fillna(0)
