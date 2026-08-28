"""ADP 抓取与解析测试。

不依赖网络：用本地构造的 HTML 片段测试解析器，用 mock 测试降级逻辑。
真实抓取由集成测试覆盖（需联网，默认跳过）。
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from fantasy_baseball.core import adp as adp_mod
from fantasy_baseball.core.adp import (
    ADPCache,
    _ADPTableParser,
    _parse_player_cell,
    parse_adp_html,
)


# -------------------------------------------------------------- 解析器测试
# 模拟 FantasyPros 的真实 HTML 结构（含省略 </tr>、嵌套 <a>/<small>）
SAMPLE_HTML = """
<table>
<thead><tr><th>Rank</th><th>Player (Team)</th><th>Yahoo</th><th>CBS</th>
<th>RTS</th><th>NFBC</th><th>FT</th><th>ESPN</th><th>AVG</th></tr></thead>
<tbody>
<tr class="mpb-player-1"><td>1</td><td class="player-label">
<a class="player-name" href="#">Shohei Ohtani</a><small> (LAD - SP,DH)</small></td>
<td>&nbsp;</td><td>1</td><td>2</td><td>1</td><td>1</td><td>1</td><td>1.0</td>
<tr class="mpb-player-2"><td>2</td><td class="player-label">
<a class="player-name" href="#">Aaron Judge</a><small> (NYY - LF,CF,RF,DH)</small> IL60</td>
<td>1</td><td>2</td><td>1</td><td>2</td><td>2</td><td>2</td><td>1.8</td>
<tr class="mpb-player-3"><td>3</td><td class="player-label">
<a class="player-name" href="#">Bobby Witt Jr.</a><small> (KC - SS)</small></td>
<td>3</td><td>3</td><td>4</td><td>3</td><td>4</td><td>4</td><td>3.6</td>
</tbody></table>
"""


def test_parser_extracts_rows():
    """解析器应提取出所有数据行（兼容省略 </tr>）。"""
    df = parse_adp_html(SAMPLE_HTML)
    assert len(df) == 3
    assert list(df.columns) == ["rank", "name", "pos", "adp"]


def test_parser_parses_names_and_positions():
    df = parse_adp_html(SAMPLE_HTML)
    assert df.iloc[0]["name"] == "Shohei Ohtani"
    assert df.iloc[0]["pos"] == "SP"
    assert df.iloc[1]["name"] == "Aaron Judge"
    assert df.iloc[1]["pos"] == "OF"  # LF 归一化为 OF


def test_parser_parses_adp_values():
    df = parse_adp_html(SAMPLE_HTML)
    assert df.iloc[0]["adp"] == pytest.approx(1.0)
    assert df.iloc[2]["adp"] == pytest.approx(3.6)


def test_parser_skips_header_and_invalid_rows():
    """表头行和非数据行应被跳过。"""
    df = parse_adp_html(SAMPLE_HTML)
    # rank 应从 1 开始，不含表头
    assert df.iloc[0]["rank"] == 1


def test_parse_player_cell_variants():
    """球员单元格解析应处理多种格式。"""
    # 标准 "LAD - SP,DH"
    name, pos, status = _parse_player_cell("Shohei Ohtani (LAD - SP,DH)")
    assert name == "Shohei Ohtani"
    assert pos == "SP"
    assert status is None

    # 带伤病状态
    name, pos, status = _parse_player_cell("Aaron Judge (NYY - RF,DH) IL60")
    assert pos == "OF"
    assert status == "IL60"

    # 无球队-分隔（只有位置）
    name, pos, status = _parse_player_cell("Some Player (DH)")
    assert pos == "UTIL"

    # 二刀流打者版
    name, pos, status = _parse_player_cell("Shohei Ohtani (Batter) (LAD - DH)")
    assert "Ohtani" in name


def test_parse_empty_html_raises():
    with pytest.raises(ValueError, match="未解析出"):
        parse_adp_html("<html><body>无表格</body></html>")


# -------------------------------------------------------------- 降级测试
def test_offline_returns_mock(tmpdir, monkeypatch):
    """离线模式（无缓存 + 禁止联网）应返回 mock 数据。"""
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    df = cache.fetch_adp(allow_network=False)
    assert len(df) == len(adp_mod._MOCK_ADP)
    assert "name" in df.columns
    assert "adp" in df.columns


def test_mock_does_not_write_cache(tmpdir):
    """修复 H3：mock 数据不写盘，避免污染真实缓存。"""
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    cache.fetch_adp(allow_network=False)
    assert not os.path.exists(adp_file), "mock ADP 不应写入缓存文件"


def test_get_player_adp_found(tmpdir):
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    # mock 数据里有 Ronald Acuña Jr.（离线查询避免联网覆盖缓存）
    adp = cache.get_player_adp("Ronald Acuña Jr.", allow_network=False)
    assert adp is not None
    assert 0 < adp < 10


def test_get_player_adp_not_found(tmpdir):
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    cache.fetch_adp(allow_network=False)
    assert cache.get_player_adp("Ghost Player", allow_network=False) is None


def test_get_player_adp_case_insensitive(tmpdir):
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    cache.fetch_adp(allow_network=False)
    # 大小写不敏感匹配
    assert cache.get_player_adp("mike trout", allow_network=False) is not None


def test_force_refresh_does_not_overwrite_with_mock(tmpdir):
    """修复 H3：force=True 且离线时，mock 不应覆盖已有真实缓存。"""
    adp_file = str(tmpdir.join("adp.csv"))
    cache = ADPCache(adp_file=adp_file)
    # 先模拟已有真实缓存（手动写入）
    import pandas as pd
    real_df = pd.DataFrame({"name": ["Real Player"], "pos": ["OF"], "adp": [1.5]})
    real_df.to_csv(adp_file, index=False)
    mtime_before = os.path.getmtime(adp_file)

    # force 刷新（离线，走 mock）——不应覆盖真实缓存
    cache.fetch_adp(force=True, allow_network=False)
    assert os.path.getmtime(adp_file) == mtime_before, "mock 不应覆盖已有缓存文件"
