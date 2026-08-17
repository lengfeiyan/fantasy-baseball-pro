"""数据库层测试：schema、连接、仓储。"""

from __future__ import annotations

import sqlite3

import pytest

from fantasy_baseball.db.repositories import (
    FaRepository,
    InjuryRepository,
    PlayerRepository,
    RosterRepository,
)
from fantasy_baseball.db.schema import create_all_tables, list_tables


def test_create_all_tables_idempotent(fresh_conn):
    """建表幂等，可多次执行。"""
    create_all_tables(fresh_conn)  # 第二次
    create_all_tables(fresh_conn)  # 第三次
    tables = list_tables(fresh_conn)
    for expected in ("hitters", "pitchers", "hitters_merged", "pitchers_merged",
                     "player_positions", "fa_pool", "injury_reports", "user_roster"):
        assert expected in tables, f"缺少表: {expected}"


def test_player_repository_merge_roundtrip(fresh_conn, sample_hitters):
    repo = PlayerRepository(fresh_conn)
    repo.replace_merged_hitters(sample_hitters)
    df = repo.get_merged_hitters()
    assert len(df) == 3
    assert "Player A" in df["name"].values


def test_player_repository_replace_clears_old(fresh_conn, sample_hitters):
    repo = PlayerRepository(fresh_conn)
    repo.replace_merged_hitters(sample_hitters)
    assert repo.count()["hitters_merged"] == 3
    # 用更少的数据替换
    repo.replace_merged_hitters([sample_hitters[0]])
    assert repo.count()["hitters_merged"] == 1


def test_player_repository_positions(fresh_conn):
    repo = PlayerRepository(fresh_conn)
    repo.replace_positions([
        {"name": "X", "pos": "OF", "team": "TM"},
        {"name": "Y", "pos": "SS", "team": None},
    ])
    df = repo.get_positions()
    assert len(df) == 2


def test_fa_repository_pool(fresh_conn):
    repo = FaRepository(fresh_conn)
    repo.replace_pool([
        {"player_id": None, "name": "Mike", "team": "LAA", "pos": "OF", "status": "available"},
        {"player_id": None, "name": "Aaron", "team": "NYY", "pos": "OF", "status": "available"},
    ])
    df = repo.get_pool()
    assert len(df) == 2
    assert repo.count() == 2

    # 按位置筛选
    of_df = repo.get_pool(position="OF")
    assert len(of_df) == 2

    # 查找
    found = repo.find_in_pool("Mike")
    assert found is not None
    assert found["pos"] == "OF"

    # 移除
    assert repo.remove_from_pool("Mike") is True
    assert repo.find_in_pool("Mike") is None


def test_injury_repository(fresh_conn):
    repo = InjuryRepository(fresh_conn)
    repo.replace_all([
        {"player_id": None, "name": "X", "injury_type": "背", "severity": "mild",
         "start_date": "2026-01-01", "expected_return": "2026-02-01", "status": "IL"},
    ])
    assert repo.count() == 1
    found = repo.find_by_name("X")
    assert found is not None
    assert found["severity"] == "mild"


def test_roster_repository(fresh_conn):
    repo = RosterRepository(fresh_conn)
    repo.add_player({"player_id": None, "name": "X", "team": "T", "pos": "OF"})
    df = repo.get_roster()
    assert len(df) == 1
    assert repo.remove_player("X") is True
    assert repo.get_roster().empty


def test_fa_pool_no_strict_fk(fresh_conn):
    """FA 池的 player_id 不强引用 hitters（FA 球员可在已选池之外）。"""
    repo = FaRepository(fresh_conn)
    # 任意 player_id 都应可插入，不触发外键约束
    pid = repo.add_to_pool({"player_id": 99999, "name": "Ghost", "team": "T",
                            "pos": "OF", "status": "available"})
    assert pid > 0
