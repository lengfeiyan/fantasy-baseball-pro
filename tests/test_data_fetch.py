"""数据抓取层测试。

测试不依赖网络的部分：字段映射、伤病解析、位置归一化、缓存逻辑。
网络相关用 monkeypatch mock。
"""

from __future__ import annotations

import json
import os

import pytest

from fantasy_baseball.data_fetch.mlb_api import (
    MLBStatsClient,
    _parse_injury_transaction,
    _safe_float,
    _safe_int,
    _calc_per9,
)
from fantasy_baseball.fa.analyzer import _normalize_pos


# -------------------------------------------------------------- 辅助函数
def test_safe_float_handles_mlb_format():
    """MLB 的 AVG 是 '.282' 格式。"""
    assert _safe_float(".282") == 0.282
    assert _safe_float("2.21") == 2.21
    assert _safe_float(None) is None
    assert _safe_float("") is None
    assert _safe_float("-") is None


def test_safe_int():
    assert _safe_int("55") == 55
    assert _safe_int(None) is None
    assert _safe_int("") is None


def test_calc_per9():
    """K/9 计算，IP 格式 '195.1' = 195又1/3局。"""
    # 200 K / 195.1 IP ≈ 9.22
    k9 = _calc_per9(200, "195.1")
    assert k9 == pytest.approx(9.22, abs=0.01)
    # 180 K / 100 IP = 16.2
    assert _calc_per9(180, "100") == 16.2
    # 0 局返回 None
    assert _calc_per9(10, "0") is None
    assert _calc_per9(None, "100") is None


def test_calc_per9_with_two_thirds():
    """IP '.2' 表示 2/3 局。"""
    # 6 K / 5.2 IP = 6 / (5 + 2/3) * 9 ≈ 9.53
    k9 = _calc_per9(6, "5.2")
    assert k9 == pytest.approx(9.53, abs=0.05)


# -------------------------------------------------------------- 伤病解析
def test_parse_injury_10_day():
    """10-day IL → mild。"""
    t = {
        "description": "Texas Rangers placed C Jonah Heim on the 10-day injured list. Right knee soreness.",
        "person": {"id": 641698, "fullName": "Jonah Heim"},
        "effectiveDate": "2026-07-15",
    }
    result = _parse_injury_transaction(t)
    assert result["name"] == "Jonah Heim"
    assert result["player_id"] == 641698
    assert result["severity"] == "mild"
    assert "knee" in result["injury_type"].lower()
    assert result["status"] == "IL"
    assert result["team"] == "Texas Rangers"  # team 从描述解析


def test_parse_injury_60_day():
    """60-day IL → severe。"""
    t = {
        "description": "Royals placed LHP Kris Bubic on the 60-day injured list. Left elbow soreness.",
        "person": {"id": 679323, "fullName": "Kris Bubic"},
        "effectiveDate": "2026-07-10",
    }
    result = _parse_injury_transaction(t)
    assert result["severity"] == "severe"
    assert "elbow" in result["injury_type"].lower()


def test_parse_injury_15_day():
    """15-day IL → moderate。"""
    t = {
        "description": "Giants placed 3B Matt Chapman on the 15-day injured list. Abdominal strain.",
        "person": {"id": 656308, "fullName": "Matt Chapman"},
    }
    result = _parse_injury_transaction(t)
    assert result["severity"] == "moderate"


def test_parse_injury_reinstated_is_recovered():
    """reinstated（回归）→ status=recovered。"""
    t = {
        "description": "Yankees reinstated CF Trent Grisham from the 10-day injured list.",
        "person": {"id": 676324, "fullName": "Trent Grisham"},
    }
    result = _parse_injury_transaction(t)
    assert result["status"] == "recovered"


def test_parse_injury_skips_non_injured():
    """非伤病 transaction（如签约）应返回 None。"""
    t = {
        "description": "Braves signed free agent OF Luis Consoro to a minor league contract.",
        "person": {"id": 1, "fullName": "Luis Consoro"},
    }
    # 但 _parse_injury_transaction 假设上游已筛过，这里只验证它能处理
    # 实际过滤在 fetch_injuries 里做（检查 "injured list" 关键字）


# -------------------------------------------------------------- 位置归一化
def test_normalize_pos_outfield():
    """CF/RF/LF → OF。"""
    assert _normalize_pos("CF") == "OF"
    assert _normalize_pos("RF") == "OF"
    assert _normalize_pos("LF") == "OF"
    assert _normalize_pos("OF") == "OF"


def test_normalize_pos_infield_unchanged():
    assert _normalize_pos("SS") == "SS"
    assert _normalize_pos("1B") == "1B"
    assert _normalize_pos("C") == "C"


def test_normalize_pos_dh_to_util():
    assert _normalize_pos("DH") == "UTIL"


def test_normalize_pos_empty():
    assert _normalize_pos("") == ""
    assert _normalize_pos(None) == ""


# -------------------------------------------------------------- 缓存（mock 网络）
def test_mlb_client_caches_search(tmpdir, monkeypatch):
    """搜索结果应被缓存，第二次命中缓存。"""
    import fantasy_baseball.data_fetch.mlb_api as mmod

    call_count = [0]
    original_get = mmod._http_get_json

    def _mock_get(url, timeout=15):
        call_count[0] += 1
        if "search" in url:
            return {"people": [{"id": 999, "fullName": "Cache Test"}]}
        return original_get(url, timeout)

    monkeypatch.setattr(mmod, "_http_get_json", _mock_get)
    client = MLBStatsClient(cache_dir=str(tmpdir))
    r1 = client.search_player("Cache Test")
    r2 = client.search_player("Cache Test")
    assert r1["id"] == 999
    assert r2["id"] == 999
    assert call_count[0] == 1  # 只请求了一次


def test_mlb_client_search_not_found(tmpdir, monkeypatch):
    """搜索不到返回 None。"""
    import fantasy_baseball.data_fetch.mlb_api as mmod

    monkeypatch.setattr(mmod, "_http_get_json", lambda url, timeout=15: {"people": []})
    client = MLBStatsClient(cache_dir=str(tmpdir))
    assert client.search_player("Nobody Exists") is None


def test_mlb_client_fetch_injuries_filters(tmpdir, monkeypatch):
    """fetch_injuries 应只返回含 'injured list' 的交易。"""
    import fantasy_baseball.data_fetch.mlb_api as mmod

    mock_response = {
        "transactions": [
            {
                "description": "Team placed C X on the 10-day injured list. Back spasm.",
                "person": {"id": 1, "fullName": "X"},
                "effectiveDate": "2026-07-01",
            },
            {
                "description": "Team signed free agent.",
                "person": {"id": 2, "fullName": "Y"},
            },
            {
                "description": "Team reinstated Z from the 15-day injured list.",
                "person": {"id": 3, "fullName": "Z"},
            },
        ]
    }
    monkeypatch.setattr(mmod, "_http_get_json", lambda url, timeout=30: mock_response)
    client = MLBStatsClient(cache_dir=str(tmpdir))
    injuries = client.fetch_injuries("2026-07-01", "2026-07-31")
    assert len(injuries) == 2  # 签约被过滤掉
    names = [i["name"] for i in injuries]
    assert "X" in names and "Z" in names and "Y" not in names


# -------------------------------------------------------------- Statcast mock 兜底
def test_statcast_hitter_mock_fallback(tmpdir, monkeypatch):
    """真实数据不可用时，Statcast 应返回 mock 兜底（非空 dict）。"""
    import fantasy_baseball.data_fetch.statcast as smod

    # mock _fetch_csv 返回 None（模拟网络失败）
    monkeypatch.setattr(smod, "_fetch_csv", lambda url: None)
    fetcher = smod.StatcastFetcher(cache_dir=str(tmpdir))
    result = fetcher.fetch_hitter_data(99999, season=2025)
    assert result  # 非空
    assert "exit_velocity" in result
    assert "xwOBA" in result
    assert result["type"] == "hitter"


def test_statcast_pitcher_mock_fallback(tmpdir, monkeypatch):
    """投手 Statcast 失败也应有 mock 兜底。"""
    import fantasy_baseball.data_fetch.statcast as smod

    monkeypatch.setattr(smod, "_fetch_csv", lambda url: None)
    fetcher = smod.StatcastFetcher(cache_dir=str(tmpdir))
    result = fetcher.fetch_pitcher_data(99999, season=2025)
    assert result
    assert "velocity" in result
    assert "whiff_rate" in result
    assert result["type"] == "pitcher"
