"""模拟战绩榜（F1）测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_baseball.core.standings import ProjectedStandings


@pytest.fixture
def full_roster():
    """接近联盟平均的 14 打者 + 9 投手阵容（统计列齐全）。

    投手人均值按 9 人撑起联盟平均队总量设计（W 78/9≈8.7、K 1280/9≈142）。
    """
    hitters = [
        {"name": f"H{i}", "pos": "OF", "R": 68, "HR": 17, "RBI": 66,
         "SB": 9, "AB": 470, "H": 126}
        for i in range(14)
    ]
    pitchers = [
        {"name": f"P{i}", "pos": "SP" if i < 5 else "RP", "W": 8.7, "SV": 7,
         "K": 142, "IP": 100, "ER": 37, "H_allow": 82, "BB_allow": 28}
        for i in range(9)
    ]
    return pd.DataFrame(hitters + pitchers)


def test_project_basic_structure(full_roster):
    result = ProjectedStandings().project(full_roster)
    cats = {r["category"]: r for r in result["categories"]}
    # 7 计数类 + 3 比率类
    assert set(cats) == {"R", "HR", "RBI", "SB", "W", "SV", "K", "AVG", "ERA", "WHIP"}
    assert result["league_size"] == 12
    assert "total_sgp" in result and "exp_total_rank" in result


def test_average_team_lands_mid_table(full_roster):
    """接近平均值的阵容：期望名次应在联盟中段（约 3~9），总 SGP 接近 0。"""
    result = ProjectedStandings().project(full_roster)
    cats = {r["category"]: r for r in result["categories"]}
    for cat in ("R", "HR", "RBI"):
        assert 2.0 <= cats[cat]["exp_rank"] <= 10.0
    assert abs(result["total_sgp"]) < 15  # 平均队不该偏离太远


def test_strong_team_ranks_high(full_roster):
    """全联盟顶级阵容：计数类期望名次应显著靠前（< 3）。"""
    strong = full_roster.copy()
    for col in ("R", "HR", "RBI", "SB"):
        strong[col] = strong[col] * 1.35
    result = ProjectedStandings().project(strong)
    cats = {r["category"]: r for r in result["categories"]}
    for cat in ("R", "HR", "RBI"):
        assert cats[cat]["exp_rank"] < 3.0, f"{cat} 顶级阵容名次应靠前: {cats[cat]}"
    assert result["total_sgp"] > 0


def test_roster_without_stats_gets_enriched(fresh_conn):
    """回归：user_roster 只有身份列 → 自动从 merged 表补统计。"""
    import sqlite3

    from fantasy_baseball.db import PlayerRepository, RosterRepository
    from fantasy_baseball.db.schema import create_all_tables

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_all_tables(conn)
    repo = PlayerRepository(conn)
    repo.replace_merged_hitters([
        {"name": "Hitter A", "pos": "OF", "R": 100, "HR": 40, "RBI": 100,
         "SB": 20, "AB": 600, "H": 180},
    ])
    repo.replace_merged_pitchers([
        {"name": "Pitcher A", "pos": "SP", "W": 15, "SV": 0, "K": 200,
         "IP": 180, "ER": 60, "H_allow": 150, "BB_allow": 50},
    ])
    roster_repo = RosterRepository(conn)
    roster_repo.add_player({"name": "Hitter A", "pos": "OF"})
    roster_repo.add_player({"name": "Pitcher A", "pos": "SP"})
    conn.commit()

    roster = roster_repo.get_roster()
    result = ProjectedStandings().project(
        roster,
        hitters_source=pd.DataFrame([
            {"name": "Hitter A", "R": 100, "HR": 40, "RBI": 100,
             "SB": 20, "AB": 600, "H": 180},
        ]),
        pitchers_source=pd.DataFrame([
            {"name": "Pitcher A", "W": 15, "SV": 0, "K": 200,
             "IP": 180, "ER": 60, "H_allow": 150, "BB_allow": 50},
        ]),
    )
    cats = {r["category"]: r for r in result["categories"]}
    assert cats["R"]["team_value"] == 100.0
    assert cats["HR"]["team_value"] == 40.0
    assert cats["K"]["team_value"] == 200.0


def test_empty_roster_raises():
    with pytest.raises(ValueError, match="阵容为空"):
        ProjectedStandings().project(pd.DataFrame())
