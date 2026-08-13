"""预测数据抓取测试。

不依赖网络：用本地构造的 HTML 片段测试解析器与列映射。
真实抓取由集成测试覆盖（需联网，默认跳过）。
"""

from __future__ import annotations

import pytest

from fantasy_baseball.data_fetch.projections import (
    _extract_team,
    _parse_table,
    _to_float,
    _HITTER_COL_MAP,
    _PITCHER_COL_MAP,
)


# 模拟 FantasyPros 打者预测表 HTML
SAMPLE_HITTER_HTML = """
<table>
<thead><tr><th>Player</th><th>AB</th><th>R</th><th>HR</th><th>RBI</th><th>SB</th>
<th>AVG</th><th>OBP</th><th>H</th><th>2B</th><th>3B</th><th>BB</th><th>SO</th>
<th>SLG</th><th>OPS</th><th>Rost%</th></tr></thead>
<tbody>
<tr class="player-1"><td class="player-label"><a class="player-name">Aaron Judge</a>
<small> (NYY - RF,DH)</small></td><td>500</td><td>110</td><td>46</td><td>114</td>
<td>9</td><td>.292</td><td>.410</td><td>146</td><td>28</td><td>0</td><td>108</td>
<td>180</td><td>.600</td><td>1.026</td><td>99%</td>
<tr class="player-2"><td class="player-label"><a class="player-name">Bobby Witt Jr.</a>
<small> (KC - SS)</small></td><td>600</td><td>101</td><td>29</td><td>93</td>
<td>34</td><td>.292</td><td>.350</td><td>175</td><td>35</td><td>5</td><td>40</td>
<td>90</td><td>.500</td><td>.863</td><td>98%</td>
</tbody></table>
"""


# 模拟投手预测表 HTML
SAMPLE_PITCHER_HTML = """
<table>
<thead><tr><th>Player</th><th>IP</th><th>K</th><th>W</th><th>SV</th><th>ERA</th>
<th>WHIP</th><th>ER</th><th>H</th><th>BB</th><th>HR</th><th>G</th><th>GS</th>
<th>L</th><th>CG</th><th>Rost%</th></tr></thead>
<tbody>
<tr class="p1"><td><a class="player-name">Tarik Skubal</a><small> (LAD - SP)</small></td>
<td>193.0</td><td>234</td><td>14</td><td>0</td><td>2.72</td><td>0.97</td>
<td>58</td><td>148</td><td>40</td><td>18</td><td>31</td><td>31</td><td>7</td>
<td>0</td><td>99%</td>
</tbody></table>
"""


def test_parse_hitter_table():
    """打者表解析应返回正确的列与数值。"""
    df = _parse_table(SAMPLE_HITTER_HTML, _HITTER_COL_MAP)
    assert len(df) == 2
    assert "Aaron Judge" in df["name"].values
    assert "HR" in df.columns
    assert "OPS" in df.columns


def test_parse_hitter_values():
    df = _parse_table(SAMPLE_HITTER_HTML, _HITTER_COL_MAP)
    judge = df[df["name"] == "Aaron Judge"].iloc[0]
    assert judge["HR"] == 46
    assert judge["RBI"] == 114
    assert judge["AVG"] == pytest.approx(0.292)
    assert judge["OPS"] == pytest.approx(1.026)


def test_parse_hitter_pos_and_team():
    """位置和球队应从 Player 列正确提取。"""
    df = _parse_table(SAMPLE_HITTER_HTML, _HITTER_COL_MAP)
    judge = df[df["name"] == "Aaron Judge"].iloc[0]
    assert judge["team"] == "NYY"
    assert judge["pos"] == "OF"  # RF 归一化为 OF


def test_parse_pitcher_table():
    df = _parse_table(SAMPLE_PITCHER_HTML, _PITCHER_COL_MAP)
    assert len(df) == 1
    skubal = df.iloc[0]
    assert skubal["name"] == "Tarik Skubal"
    assert skubal["W"] == 14
    assert skubal["ERA"] == pytest.approx(2.72)


def test_extract_team():
    assert _extract_team("Aaron Judge (NYY - RF,DH)") == "NYY"
    assert _extract_team("Tarik Skubal (LAD - SP)") == "LAD"
    assert _extract_team("Some Player") == ""


def test_to_float():
    assert _to_float(".292") == 0.292
    assert _to_float("46") == 46.0
    assert _to_float("") is None
    assert _to_float(None) is None
    assert _to_float("-") is None


def test_parse_empty_html():
    """空 HTML 应返回空 DataFrame。"""
    df = _parse_table("<html></html>", _HITTER_COL_MAP)
    assert df.empty


def test_ingest_from_web_writes_merged(tmpdir, monkeypatch):
    """ingest_from_web 应把数据写入 merged 表（mock 网络）。"""
    import sqlite3
    from fantasy_baseball.db.schema import create_all_tables
    from fantasy_baseball.core.ingestor import DataIngestor
    import pandas as pd

    # mock fetch_projections 返回固定数据
    mock_hitters = pd.DataFrame([
        {"name": "Test A", "team": "TM", "pos": "OF", "R": 100, "HR": 30,
         "RBI": 90, "SB": 20, "AVG": 0.300, "OBP": 0.380, "SLG": 0.520, "OPS": 0.900, "PA": 600},
    ])
    mock_pitchers = pd.DataFrame([
        {"name": "Test P", "team": "TM", "pos": "SP", "IP": 180, "K": 200,
         "W": 14, "SV": 0, "ERA": 3.00, "WHIP": 1.10, "BB": 40, "H": 150,
         "HR": 18, "ER": 60, "G": 30, "GS": 30, "L": 6},
    ])

    import fantasy_baseball.data_fetch.projections as pmod
    monkeypatch.setattr(pmod, "fetch_projections",
                        lambda pt, season: mock_hitters if pt == "hitters" else mock_pitchers)
    monkeypatch.setattr(
        "fantasy_baseball.core.ingestor.fetch_projections" if False else "fantasy_baseball.data_fetch.projections.fetch_projections",
        lambda pt, season: mock_hitters if pt == "hitters" else mock_pitchers,
    )

    db_path = str(tmpdir.join("test.db"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    create_all_tables(conn)

    ing = DataIngestor(conn=conn)
    counts = ing.ingest_from_web(season=2026)
    assert counts["hitters_merged"] == 1
    assert counts["pitchers_merged"] == 1
    assert counts["positions"] == 2
    conn.close()
