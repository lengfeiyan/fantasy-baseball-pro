"""F7 新秀雷达测试。

覆盖：Pipeline 内嵌数据解析、MiLB Statcast 聚合 CSV 解析（含 BOM/列名差异）、
接近度启发式、层级判定优先级、比率指标刻度、雷达端到端构建（全 fake 不联网）、
快照入库回读、analyzer 新秀加成开关行为（默认关 = 行为不变）。
"""

from __future__ import annotations

import json

import pandas as pd
import pytest


# ============================================================ Pipeline 解析

def _fake_prospect_html(entries: list) -> str:
    """构造含内嵌 var data 的假页面（前后带干扰内容与嵌套括号字符串）。"""
    return (
        "<html><head><title>mlb</title></head><body><script>\n"
        "var ddlType = 'prospects';\n"
        f"var data = {json.dumps(entries, ensure_ascii=False)};\n"
        "var minPA = 1;\n"
        "</script></body></html>"
    )


def test_extract_data_var_parses_embedded_array():
    from fantasy_baseball.data_fetch.pipeline import extract_data_var

    entries = [
        {"name": "Jesús Made", "href": "<a href=\"x\">Made [BOS]</a>",
         "playerId": 815908, "age": 19, "position": "SS", "rank": 1,
         "team": "mil", "teamId": 158, "slug": "jesus-made-815908",
         "sportAbbrev": "AA", "avg": ".270",
         "battingStats": {"gamesPlayed": 113, "strikeOuts": 76}},
    ]
    data = extract_data_var(_fake_prospect_html(entries))
    assert data is not None and len(data) == 1
    assert data[0]["playerId"] == 815908
    # 字符串内的 "]" 不得破坏方括号配平
    assert data[0]["href"].endswith("[BOS]</a>")


def test_extract_data_var_missing_block_returns_none():
    from fantasy_baseball.data_fetch.pipeline import extract_data_var

    assert extract_data_var("<html><body>no data here</body></html>") is None


def test_extract_data_var_unclosed_returns_none():
    from fantasy_baseball.data_fetch.pipeline import extract_data_var

    assert extract_data_var("<script>var data = [{\"a\": 1}</script>") is None


def test_extract_data_var_bad_json_returns_none():
    from fantasy_baseball.data_fetch.pipeline import extract_data_var

    assert extract_data_var("<script>var data = [{broken}];</script>") is None


def test_highest_level_tokens():
    from fantasy_baseball.data_fetch.pipeline import highest_level

    assert highest_level("AA") == "AA"
    assert highest_level("AAA") == "AAA"
    assert highest_level("MLB") == "MLB"
    assert highest_level("ALL (2)") == "MULTI"
    assert highest_level("") == ""
    assert highest_level(None) == ""


def test_normalize_prospect_unifies_stats_key():
    from fantasy_baseball.data_fetch.pipeline import normalize_prospect

    hitter = normalize_prospect({"name": "A B", "playerId": 1, "rank": 5,
                                 "age": 20, "position": "SS", "team": "tm",
                                 "sportAbbrev": "AA", "avg": ".300",
                                 "battingStats": {"strikeOuts": 10}})
    assert hitter["season_stats"] == {"strikeOuts": 10}
    assert hitter["top_level"] == "AA"

    pitcher = normalize_prospect({"name": "C D", "playerId": 2, "rank": 6,
                                  "position": "RHP", "sportAbbrev": "ALL (2)",
                                  "pitchingStats": {"inningsPitched": 90}})
    assert pitcher["season_stats"] == {"inningsPitched": 90}
    assert pitcher["top_level"] == "MULTI"


# ============================================================ MiLB CSV 解析

_BATCH_CSV = (
    '\ufeff"pitches","player_id","player_name","total_pitches","whiffs",'
    '"swing_miss_percent","launch_speed","xwoba","velocity"\n'
    '"2088","809707","Condon, Charlie","2088","249","19.2","89.5",".35",""\n'
    '"589","689981","Ryan, River","591","81","","",".277","93.4"\n'
)


def test_parse_aggregate_csv_batch_columns_and_bom():
    from fantasy_baseball.data_fetch.milb_statcast import _parse_aggregate_csv

    rows = _parse_aggregate_csv(_BATCH_CSV)
    assert rows is not None and len(rows) == 2
    condon = next(r for r in rows if r["player_id"] == 809707)
    # BOM+引号损坏的首列被清洗，total_pitches 正确转数值
    assert condon["total_pitches"] == 2088
    assert condon["swing_miss_percent"] == 19.2
    assert condon["xwoba"] == 0.35
    # 空值列直接缺失而非 NaN 字符串
    ryan = next(r for r in rows if r["player_id"] == 689981)
    assert "swing_miss_percent" not in ryan
    assert ryan["velocity"] == 93.4


def test_parse_aggregate_csv_empty_returns_none():
    from fantasy_baseball.data_fetch.milb_statcast import _parse_aggregate_csv

    assert _parse_aggregate_csv(None) is None
    assert _parse_aggregate_csv("") is None
    assert _parse_aggregate_csv("garbage") is None


def test_fetch_tracked_players_rejects_bad_type():
    """参数白名单校验不发起网络请求。"""
    from fantasy_baseball.data_fetch.milb_statcast import MilbStatcastFetcher

    assert MilbStatcastFetcher().fetch_tracked_players("goalie") is None


# ============================================================ 接近度启发式

def _prospect(levels, age, mlb_id=1):
    from fantasy_baseball.data_fetch.pipeline import highest_level

    return {"levels": levels, "top_level": highest_level(levels), "age": age,
            "mlb_id": mlb_id, "name": "X", "rank": 1, "position": "SS",
            "team": "t", "team_id": 1}


def test_compute_proximity_matrix():
    from fantasy_baseball.core.rookies import compute_proximity

    assert compute_proximity(_prospect("MLB", 23), {}) == "已登板"
    assert compute_proximity(_prospect("AAA", 22), {}) == "近"
    assert compute_proximity(_prospect("AA", 21), {}) == "近"
    assert compute_proximity(_prospect("ALL (2)", 20), {}) == "近"
    assert compute_proximity(_prospect("ALL (3)", 19), {}) == "中"
    assert compute_proximity(_prospect("A+", 19), {}) == "中"
    assert compute_proximity(_prospect("A", 19), {}) == "远"
    assert compute_proximity(_prospect("ROK", 18), {}) == "远"
    # AAA 字样不得被 AA 的子串匹配误判（levels 只含 AAA 时走第一分支，同近）
    # 无级别标记但有 tracking 记录的成年球员保守视为近
    assert compute_proximity(_prospect("ALL (2)", 22), {1: {"stats": {}}}) == "近"


def test_compute_proximity_aa_not_swallowed_by_aaa_substring():
    """levels 同时含 AAA 与 AA 时仍应为近（顺序分支），且不会被 replace 破坏。"""
    from fantasy_baseball.core.rookies import compute_proximity

    assert compute_proximity(_prospect("ALL (3)", 21), {}) == "近"


# ============================================================ 层级判定与指标

def _radar():
    from fantasy_baseball.core.rookies import RookieRadar

    return RookieRadar()


def test_tier_precedence_b_over_c():
    from fantasy_baseball.core.rookies import RookieRadar, compute_proximity

    radar = _radar()
    prospect = _prospect("ALL (2)", 20, mlb_id=809707)
    idx = {809707: {"player_type": "batter",
                    "stats": {"total_pitches": 2088, "swing_miss_percent": 19.2,
                              "launch_speed": 89.5, "xwoba": 0.35}}}
    tier, metrics, signals = radar._assign_tier(
        prospect, True, compute_proximity(prospect, idx), idx, {}, None, False, 2026, False
    )
    assert tier == "B"
    assert metrics["avg_ev"] == 89.5
    assert metrics["whiff_rate"] == pytest.approx(19.2)
    assert "MiLB Statcast" in signals

    # 无 tracking → 落 C 层（比率统计）
    prospect2 = _prospect("AA", 19, mlb_id=999)
    stats = {"kPercent": 14.7, "bbPercent": 10.5}
    tier2, metrics2, _ = radar._assign_tier(
        {**prospect2, "season_stats": stats}, True,
        compute_proximity(prospect2, idx), idx, {}, None, False, 2026, False
    )
    assert tier2 == "C"
    assert metrics2["k_percent"] == pytest.approx(14.7)


def test_tier_c_metrics_pitcher_computes_from_bf():
    """投手 strikePercentage 实为好球率不可用，K% 必须用 SO/BF 自算（实测列名）。"""
    from fantasy_baseball.core.rookies import RookieRadar

    metrics, signals = RookieRadar._tier_c_metrics(
        {"strikeOuts": 143, "baseOnBalls": 18, "battersFaced": 374,
         "strikePercentage": 0.69}, is_hitter=False)
    assert metrics["k_percent"] == pytest.approx(143 / 374 * 100, rel=1e-3)
    assert metrics["bb_percent"] == pytest.approx(18 / 374 * 100, rel=1e-3)
    assert "K%" in signals


def test_tier_c_metrics_missing_stats_returns_empty():
    from fantasy_baseball.core.rookies import RookieRadar

    assert RookieRadar._tier_c_metrics({}, is_hitter=True) == ({}, "")


# ============================================================ 端到端构建（全 fake）

class _FakePipeline:
    """返回固定榜单的假抓取器。"""

    def fetch_top_prospects(self, season=None, force=False):
        return [
            {"rank": 1, "name": "Alpha Pros", "mlb_id": 101, "age": 20,
             "position": "SS", "team": "aaa", "team_id": 1, "levels": "AAA",
             "top_level": "AAA", "avg": ".300", "era": None,
             "season_stats": {"kPercent": 15.0, "bbPercent": 12.0}},
            {"rank": 2, "name": "Beta Yound", "mlb_id": 102, "age": 18,
             "position": "RHP", "team": "bbb", "team_id": 2, "levels": "A",
             "top_level": "A", "avg": None, "era": 3.5,
             "season_stats": {"strikeOuts": 100, "baseOnBalls": 30,
                              "battersFaced": 400}},
            {"rank": 3, "name": "Gamma Old", "mlb_id": 103, "age": 25,
             "position": "OF", "team": "ccc", "team_id": 3, "levels": "MLB",
             "top_level": "MLB", "avg": ".250", "era": None,
             "season_stats": {"kPercent": 25.0, "bbPercent": 8.0}},
        ]


class _FakeMilb:
    def build_player_index(self, season=None, force=False):
        return {101: {"player_type": "batter",
                      "stats": {"total_pitches": 1000, "swings": 500,
                                "whiffs": 75, "swing_miss_percent": 15.0,
                                "launch_speed": 91.0, "xwoba": 0.400}}}

    def fetch_spring_stats(self, *a, **k):
        return None


def _fake_adp_df():
    return pd.DataFrame([
        {"name": "Alpha Pros", "adp": 210.0},
        {"name": "Gamma Old", "adp": 180.0},
    ])


def test_build_end_to_end_with_fakes():
    from fantasy_baseball.core.rookies import RookieRadar

    radar = RookieRadar(pipeline_fetcher=_FakePipeline(),
                        milb_fetcher=_FakeMilb(), adp_df=_fake_adp_df(),
                        deep_adp=False)
    df = radar.build(season=2026)
    # Beta（A，18 岁，远）默认被剔除
    names = set(df["name"])
    assert names == {"Alpha Pros", "Gamma Old"}
    by_name = df.set_index("name")
    # Alpha：AAA + tracking → B 层
    assert by_name.loc["Alpha Pros", "tier"] == "B"
    # Gamma：MLB 标记 → 已登板；百分位快照缺失（空索引）→ 落 C
    assert by_name.loc["Gamma Old", "proximity"] == "已登板"
    assert by_name.loc["Gamma Old", "tier"] == "C"
    # 价值差：ADP 210 → 榜内 ADP 排名第 2（180 更小），2 - 1 = +1
    assert by_name.loc["Alpha Pros", "value_gap"] == pytest.approx(1.0)
    # 综合分降序
    assert df["composite"].is_monotonic_decreasing


def test_build_include_far_keeps_far_players():
    from fantasy_baseball.core.rookies import RookieRadar

    radar = RookieRadar(pipeline_fetcher=_FakePipeline(),
                        milb_fetcher=_FakeMilb(), adp_df=pd.DataFrame(),
                        deep_adp=False)
    df = radar.build(include_far=True, season=2026)
    assert set(df["name"]) == {"Alpha Pros", "Beta Yound", "Gamma Old"}
    beta = df.set_index("name").loc["Beta Yound"]
    assert beta["proximity"] == "远"
    assert beta["tier"] == "C"  # 投手 K%/BB% 兜底


def test_build_raises_runtimeerror_on_fetch_failure():
    from fantasy_baseball.core.rookies import RookieRadar

    class _Broken:
        def fetch_top_prospects(self, season=None, force=False):
            return None

    radar = RookieRadar(pipeline_fetcher=_Broken(),
                        milb_fetcher=_FakeMilb(), adp_df=pd.DataFrame())
    with pytest.raises(RuntimeError):
        radar.build(season=2026)


# ============================================================ 快照入库回读

def test_save_snapshot_roundtrip(isolated_db):
    from fantasy_baseball.core.rookies import RookieRadar
    from fantasy_baseball.db import ProspectRepository, db_session

    df = pd.DataFrame([
        {"rank": 1, "name": "Alpha Pros", "mlb_id": 101, "position": "SS",
         "age": 20, "team": "aaa", "levels": "AAA", "top_level": "AAA",
         "proximity": "近", "tier": "B", "composite": 0.81,
         "value_gap": 1.0, "adp": 210.0, "signals": "x"},
        {"rank": 2, "name": "Beta", "mlb_id": 102, "position": "RHP",
         "age": 21, "team": "bbb", "levels": "AA", "top_level": "AA",
         "proximity": "近", "tier": "C", "composite": 0.75,
         "value_gap": None, "adp": None, "signals": "y"},
    ])
    saved = RookieRadar.save_snapshot(df, season=2026)
    assert saved == 2
    with db_session() as conn:
        snap = ProspectRepository(conn).get_latest_snapshot(2026)
    assert len(snap) == 2
    assert set(snap["name"]) == {"Alpha Pros", "Beta"}
    assert snap.iloc[0]["composite"] == pytest.approx(0.81)


def test_snapshot_rank_history(isolated_db):
    from fantasy_baseball.core.rookies import RookieRadar
    from fantasy_baseball.db import ProspectRepository, db_session

    def _row(rank, composite):
        return {"rank": rank, "name": "Riser", "mlb_id": 9, "position": "OF",
                "age": 20, "team": "t", "levels": "AA", "top_level": "AA",
                "proximity": "近", "tier": "C", "composite": composite,
                "value_gap": None, "adp": None, "signals": ""}

    RookieRadar.save_snapshot(pd.DataFrame([_row(3, 0.80)]), season=2026)
    RookieRadar.save_snapshot(pd.DataFrame([_row(1, 0.72)]), season=2026)
    with db_session() as conn:
        hist = ProspectRepository(conn).rank_history("Riser", 2026)
    assert len(hist) == 2
    assert list(hist["composite"]) == [0.80, 0.72]
    # rank 从 3 升到 1（post-hype / 上升检测的原始序列）
    assert list(hist["rank"]) == [3, 1]


# ============================================================ analyzer 加成开关

@pytest.fixture
def _reset_rookie_index():
    """类属性索引在用例间复位（懒加载缓存不得跨用例泄漏）。"""
    from fantasy_baseball.fa.analyzer import FAAnalyzer

    FAAnalyzer._rookie_index = None
    yield
    FAAnalyzer._rookie_index = None


def _seed_snapshot(conn, name, composite):
    ProspectRepository = pytest.importorskip(
        "fantasy_baseball.db").ProspectRepository
    ProspectRepository(conn).save_snapshot(
        [{"rank": 1, "name": name, "mlb_id": 1, "position": "SS", "age": 20,
          "team": "t", "levels": "AA", "top_level": "AA", "proximity": "近",
          "tier": "C", "composite": composite, "value_gap": None,
          "adp": None, "payload": None}], season=2026)


def test_rookie_boost_disabled_by_default(isolated_db, _reset_rookie_index):
    """默认关：不开开关时加成为 None——FA 评分行为与历史完全一致（回归保证）。"""
    from fantasy_baseball.config import get_config
    from fantasy_baseball.db import db_session
    from fantasy_baseball.fa.analyzer import FAAnalyzer

    _seed_snapshot(isolated_db, "Alpha Pros", 0.8)
    analyzer = FAAnalyzer(conn=isolated_db)
    boost = analyzer._apply_rookie_boost("Alpha Pros")
    assert boost is None  # config 默认 enabled: false
    assert get_config()["fa_analyzer"]["rookie_boost"]["enabled"] is False


def test_rookie_boost_enabled_multiplies_and_offlist_ignores(
        isolated_db, monkeypatch, _reset_rookie_index):
    from fantasy_baseball import config as cfgmod
    from fantasy_baseball.fa import analyzer as analyzer_mod
    from fantasy_baseball.fa.analyzer import FAAnalyzer

    _seed_snapshot(isolated_db, "Alpha Pros", 0.8)
    base_cfg = cfgmod.get_config()
    base_cfg.setdefault("fa_analyzer", {})["rookie_boost"] = {
        "enabled": True, "factor": 0.05}
    # analyzer 持有自己的 import 引用，必须 patch 它命名空间里的 get_config
    monkeypatch.setattr(analyzer_mod, "get_config", lambda: base_cfg)

    analyzer = FAAnalyzer(conn=isolated_db)
    boost = analyzer._apply_rookie_boost("alpha   pros")  # 大小写/空白规范化
    assert boost is not None
    assert boost["multiplier"] == pytest.approx(1 + 0.05 * 0.8)
    # 未上榜球员 → None
    assert analyzer._apply_rookie_boost("Nobody Here") is None


# ============================================================ deep ADP（2）

def _deep_page(rows):
    """构造 FP 风格 ADP 页（mpb-player 行 + fp-player-name 属性 + 末列均值）。"""
    trs = []
    for name, adp in rows:
        adp_txt = str(adp)
        trs.append(
            f'<tr class="mpb-player-1"><td>1</td>'
            f'<td class="player-label"><a class="fp-player-link" '
            f'fp-player-name="{name}" href="#">{name}</a></td>'
            f'<td>1</td><td>{adp_txt}</td></tr>'
        )
    return "<table>" + "".join(trs) + "</table>"


def test_parse_deep_adp_html_position_page_columns():
    """位置页比 overall 页多一个位置顺位列——属性取名对两种页面统一适用。"""
    from fantasy_baseball.core.adp import _parse_deep_adp_html

    html = _deep_page([("Shohei Ohtani", 1.0), ("Tarik Skubal", 6.8)])
    parsed = _parse_deep_adp_html(html)
    assert parsed == {"Shohei Ohtani": 1.0, "Tarik Skubal": 6.8}


def test_parse_deep_adp_html_skips_nonnumeric_tail():
    from fantasy_baseball.core.adp import _parse_deep_adp_html

    html = ('<tr class="mpb-player-9"><td>9</td>'
            '<td class="player-label"><a fp-player-name="No Adp"></a></td>'
            '<td>—</td></tr>')
    assert _parse_deep_adp_html(html) == {}


def test_fetch_deep_adp_overall_preferred_position_fills(tmpdir, monkeypatch):
    """overall 值优先，位置页只回填缺失姓名（同一球员不被位置页覆盖）。"""
    import fantasy_baseball.core.adp as adp_mod

    pages = {
        "overall": _deep_page([("Alpha", 210.0), ("Beta", 305.5)]),
        "sp": _deep_page([("Alpha", 205.0), ("Gamma Deep", 780.0)]),
        "rp": _deep_page([("Delta RP", 512.0)]),
    }

    def fake_fetch_html(url):
        for page, html in pages.items():
            if f"/{page}." in url:
                return html
        return "<html></html>"

    monkeypatch.setattr(adp_mod, "_fetch_html", fake_fetch_html)
    df = adp_mod.fetch_deep_adp(cache_dir=str(tmpdir))
    assert df is not None
    m = df.set_index("name")["adp"].to_dict()
    assert m["Alpha"] == 210.0          # overall 优先，未被 sp 页的 205 覆盖
    assert m["Gamma Deep"] == 780.0     # 位置页回填
    assert m["Delta RP"] == 512.0
    # 值域覆盖超过 overall 榜的 ~600 人口径
    assert max(m.values()) >= 780.0


def test_fetch_deep_adp_all_fail_returns_none(tmpdir, monkeypatch):
    import fantasy_baseball.core.adp as adp_mod

    def broken(url):
        raise OSError("network down")

    monkeypatch.setattr(adp_mod, "_fetch_html", broken)
    assert adp_mod.fetch_deep_adp(cache_dir=str(tmpdir)) is None


# ============================================================ 级别归因（3）

class _FakeStatsClient:
    """批量 currentTeam + 球队级别映射的假客户端。

    102 模拟"40 人名单未登板"（现属 MLB 组织但 GP=0）→ 不给级别。
    """

    def fetch_people_current_teams(self, person_ids, season=None):
        return {
            101: {"team_id": 5015, "mlb_gp": 0},   # AA 附属球队
            102: {"team_id": 136, "mlb_gp": 0},    # MLB 组织但未登板 → None
            103: None,
            104: {"team_id": 136, "mlb_gp": 2},    # 真升班（GP>0）
        }

    def fetch_milb_team_level_map(self, season=None):
        return {5015: "AA", 136: "MLB", 999: "A+"}


def test_fetch_people_current_teams_parses_hydrate(tmpdir, monkeypatch):
    from fantasy_baseball.data_fetch import mlb_api

    def fake_get_json(url, **kwargs):
        assert "hydrate=currentTeam" in url
        return {"people": [
            {"id": 815908, "currentTeam": {"id": 5015},
             "stats": [{"splits": [{"sport": {"id": 12},
                                    "stat": {"gamesPlayed": 114}}]}]},
            {"id": 807739, "currentTeam": {"id": 136},
             "stats": [{"splits": [{"sport": {"id": 1},
                                    "stat": {"gamesPlayed": 2}}]}]},
        ]}

    monkeypatch.setattr(mlb_api, "_http_get_json", fake_get_json)
    client = mlb_api.MLBStatsClient(cache_dir=str(tmpdir))
    result = client.fetch_people_current_teams([815908, 807739])
    # 只累计 sportId=1（MLB）的出场数
    assert result == {815908: {"team_id": 5015, "mlb_gp": 0},
                      807739: {"team_id": 136, "mlb_gp": 2}}


def test_fetch_people_current_teams_network_fail_returns_empty(tmpdir, monkeypatch):
    from fantasy_baseball.data_fetch import mlb_api

    monkeypatch.setattr(mlb_api, "_http_get_json", lambda url, **k: None)
    client = mlb_api.MLBStatsClient(cache_dir=str(tmpdir))
    assert client.fetch_people_current_teams([1, 2]) == {}


def test_fetch_milb_team_level_map(tmpdir, monkeypatch):
    from fantasy_baseball.data_fetch import mlb_api

    def fake_get_json(url):
        if "sportId=1&" in url:
            return {"teams": [{"id": 136, "name": "Seattle Mariners"}]}
        if "sportId=12&" in url:
            return {"teams": [{"id": 5015, "name": "Biloxi Shuckers"}]}
        return {"teams": []}

    monkeypatch.setattr(mlb_api, "_http_get_json", fake_get_json)
    client = mlb_api.MLBStatsClient(cache_dir=str(tmpdir))
    mapping = client.fetch_milb_team_level_map()
    assert mapping == {136: "MLB", 5015: "AA"}


def test_compute_proximity_resolved_level_overrides_heuristic():
    """精确归因优先于级别标记/年龄启发式（9 月升班、MULTI 误判场景）。"""
    from fantasy_baseball.core.rookies import compute_proximity

    # MULTI 19 岁按启发式是"中"，现属 AA 归因后应为"近"
    p = _prospect("ALL (2)", 19)
    assert compute_proximity(p, {}) == "中"
    assert compute_proximity(p, {}, resolved_level="AA") == "近"
    # 现属 MLB 组织（如 9 月扩编升班）→ 已登板，即便 Pipeline 未标 MLB
    assert compute_proximity(p, {}, resolved_level="MLB") == "已登板"
    assert compute_proximity(_prospect("AA", 21), {}, resolved_level="A+") == "中"
    assert compute_proximity(_prospect("AAA", 22), {}, resolved_level="A") == "远"
    # 未归因 → 启发式不变
    assert compute_proximity(_prospect("AA", 21), {}) == "近"


def test_metric_score_splits_band_pools():
    """同级 K% 在不同级别带内得分不同（消除低级别 K% 注水偏置）。"""
    from fantasy_baseball.core.rookies import RookieRadar

    def _row(name, level, k):
        return {"name": name, "tier": "C", "is_hitter": True, "level": level,
                "proximity": "近", "pipeline_rank": 1, "metrics":
                {"k_percent": k, "bb_percent": None}, "value_gap": None}

    df = pd.DataFrame([
        _row("LowK", "AA", 10.0),      # upper 带
        _row("MidK", "AA", 20.0),      # upper 带
        _row("HighK", "AA", 30.0),     # upper 带
        _row("SameK20_LowBand", "A", 20.0),  # lower 带仅 1 人 → 池不足退回全池
    ])
    radar = _radar()
    out = radar._score(df).set_index("name")
    # 同为 K% 20：upper 带内是最高（好），退回全池后居中——得分必须不同
    assert (out.loc["MidK", "metric_score"] >
            out.loc["SameK20_LowBand", "metric_score"])
    # K% 越低越好：LowK(10) 应高于 MidK(20)
    assert out.loc["LowK", "metric_score"] > out.loc["MidK", "metric_score"]


def test_build_uses_resolved_level_column():
    """端到端：归因结果写 level 列并驱动接近度；40 人未登板者退启发式。"""
    from fantasy_baseball.core.rookies import RookieRadar

    radar = RookieRadar(pipeline_fetcher=_FakePipeline(),
                        milb_fetcher=_FakeMilb(), adp_df=_fake_adp_df(),
                        stats_client=_FakeStatsClient(), deep_adp=False)
    df = radar.build(season=2026)
    by_name = df.set_index("name")
    # Alpha（101 → 5015 → AA）：级别列显示归因值
    assert by_name.loc["Alpha Pros", "level"] == "AA"
    # Beta（102 → MLB 组织但 GP=0）＝40 人名单未登板：不给级别（退 top_level），
    # levels="A" 启发式 → 远，默认被剔除
    assert "Beta Yound" not in by_name.index
    df_all = radar.build(include_far=True, season=2026)
    beta = df_all.set_index("name").loc["Beta Yound"]
    assert beta["level"] == "A"      # 退回 Pipeline 标记
    assert beta["proximity"] == "远"
    # Gamma（103 → 无 team 信息）未归因 → 启发式（levels 含 MLB）仍判已登板
    assert by_name.loc["Gamma Old", "level"] == "MLB"
    assert by_name.loc["Gamma Old", "proximity"] == "已登板"
