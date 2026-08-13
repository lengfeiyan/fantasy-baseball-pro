"""评分模型测试。"""

from __future__ import annotations

import pytest

from fantasy_baseball.core.scoring import ScoringModel
from fantasy_baseball.db import PlayerRepository


def _seed_merged(conn, hitters, pitchers):
    """填充 merged 表。"""
    repo = PlayerRepository(conn)
    repo.replace_merged_hitters(hitters)
    repo.replace_merged_pitchers(pitchers)


def test_calculate_vorp_basic(fresh_conn, sample_hitters, sample_pitchers):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    sm = ScoringModel(conn=fresh_conn)
    df = sm.calculate_vorp()
    assert len(df) == 5  # 3 打者 + 2 投手
    assert "vorp" in df.columns
    assert "vorp_upside" in df.columns
    assert "vorp_floor" in df.columns
    assert "rank" in df.columns
    assert df["rank"].tolist() == [1, 2, 3, 4, 5]


def test_vorp_sorted_descending(fresh_conn, sample_hitters, sample_pitchers):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    df = ScoringModel(conn=fresh_conn).calculate_vorp()
    vorps = df["vorp"].tolist()
    assert vorps == sorted(vorps, reverse=True)


def test_vorp_floor_non_negative(fresh_conn, sample_hitters, sample_pitchers):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    df = ScoringModel(conn=fresh_conn).calculate_vorp()
    assert (df["vorp_floor"] >= 0).all()


def test_player_type_assigned(fresh_conn, sample_hitters, sample_pitchers):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    df = ScoringModel(conn=fresh_conn).calculate_vorp()
    types = set(df["player_type"])
    assert "hitter" in types
    assert "pitcher" in types


def test_empty_db_raises(fresh_conn):
    """无数据时应报错。"""
    sm = ScoringModel(conn=fresh_conn)
    with pytest.raises(ValueError, match="没有"):
        sm.calculate_vorp()


def test_generate_rankings(tmpdir, fresh_conn, sample_hitters, sample_pitchers, monkeypatch):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    out = str(tmpdir.join("rankings.csv"))
    monkeypatch.setattr(
        "fantasy_baseball.core.scoring.resolve_path", lambda p: out
    )
    sm = ScoringModel(conn=fresh_conn)
    path = sm.generate_rankings(out)
    assert path == out

    import pandas as pd
    df = pd.read_csv(path)
    assert len(df) == 5
    assert df.iloc[0]["rank"] == 1
