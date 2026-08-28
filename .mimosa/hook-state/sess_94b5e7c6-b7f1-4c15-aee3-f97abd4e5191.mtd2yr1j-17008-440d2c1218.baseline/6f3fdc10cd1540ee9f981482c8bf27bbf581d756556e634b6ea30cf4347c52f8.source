"""阵容验证测试（重点验证除零 bug 修复）。"""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_baseball.core.roster_validator import RosterValidator


def _write_log(tmpdir, rows):
    path = tmpdir.join("draft_log.csv")
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return str(path)


def test_validate_complete_roster(tmpdir):
    """完整阵容应判定合规。"""
    rows = [
        {"round": 1, "name": "C1", "team": "T", "pos": "C", "vorp": 50},
        {"round": 2, "name": "1B1", "team": "T", "pos": "1B", "vorp": 40},
        {"round": 3, "name": "OF1", "team": "T", "pos": "OF", "vorp": 30},
    ]
    path = _write_log(tmpdir, rows)
    v = RosterValidator()
    result = v.validate_roster(path)
    assert isinstance(result.is_valid, bool)
    assert "C" in result.pos_counts
    assert result.pos_counts["C"] == 1


def test_validate_missing_position(tmpdir):
    """缺位置应判定不合规并给建议。"""
    rows = [
        {"round": 1, "name": "C1", "team": "T", "pos": "C", "vorp": 50},
        {"round": 2, "name": "C2", "team": "T", "pos": "C", "vorp": 40},
    ]
    path = _write_log(tmpdir, rows)
    v = RosterValidator()
    result = v.validate_roster(path)
    assert not result.is_valid
    assert len(result.suggestions) > 0


def test_nonexistent_file(tmpdir):
    v = RosterValidator()
    result = v.validate_roster(str(tmpdir.join("nonexistent.csv")))
    assert not result.is_valid


def test_analyze_strength_no_division_by_zero(tmpdir):
    """只有打者、无投手时不应除零崩溃。"""
    rows = [
        {"round": 1, "name": "H1", "team": "T", "pos": "OF", "vorp": 50},
        {"round": 2, "name": "H2", "team": "T", "pos": "1B", "vorp": 40},
    ]
    path = _write_log(tmpdir, rows)
    v = RosterValidator()
    strength = v.analyze_roster_strength(path)
    assert strength is not None
    assert strength.pitchers_vorp == 0.0
    # 关键：除零修复，ratio 应为 None
    assert strength.hitter_pitcher_ratio is None
    assert strength.total_vorp == 90.0


def test_analyze_strength_with_pitchers(tmpdir):
    rows = [
        {"round": 1, "name": "H1", "team": "T", "pos": "OF", "vorp": 60},
        {"round": 2, "name": "P1", "team": "T", "pos": "SP", "vorp": 30},
    ]
    path = _write_log(tmpdir, rows)
    v = RosterValidator()
    strength = v.analyze_roster_strength(path)
    assert strength.hitter_pitcher_ratio == pytest.approx(2.0)


# ============================================================
# 全联盟日志的用户队过滤（审计高危项回归：旧实现拿 12 队日志对照单队槽位）
# ============================================================
def _full_league_log():
    """两队的迷你全联盟日志，team 1 是用户（is_user_pick=True）。"""
    return [
        {"round": 1, "team": 1, "name": "U1", "pos": "OF", "vorp": 60, "is_user_pick": True},
        {"round": 1, "team": 2, "name": "O1", "pos": "OF", "vorp": 55, "is_user_pick": False},
        {"round": 2, "team": 1, "name": "U2", "pos": "SP", "vorp": 30, "is_user_pick": True},
        {"round": 2, "team": 2, "name": "O2", "pos": "OF", "vorp": 50, "is_user_pick": False},
        {"round": 3, "team": 1, "name": "U3", "pos": "C", "vorp": 20, "is_user_pick": True},
        {"round": 3, "team": 2, "name": "O3", "pos": "OF", "vorp": 45, "is_user_pick": False},
    ]


def test_validate_filters_user_team_from_full_log(tmpdir):
    """全联盟日志：位置计数只统计用户队，不再恒为「超编」。"""
    path = _write_log(tmpdir, _full_league_log())
    result = RosterValidator().validate_roster(path)
    assert result.pos_counts == {"OF": 1, "SP": 1, "C": 1}


def test_validate_explicit_team_id_overrides(tmpdir):
    """显式 team_id 优先于 is_user_pick：可查看其他球队的阵容。"""
    path = _write_log(tmpdir, _full_league_log())
    result = RosterValidator().validate_roster(path, team_id=2)
    assert result.pos_counts == {"OF": 3}


def test_analyze_strength_scoped_to_user_team(tmpdir):
    """强度分析只算用户队：总 VORP = 60+30+20，而非全联盟 260。"""
    path = _write_log(tmpdir, _full_league_log())
    strength = RosterValidator().analyze_roster_strength(path)
    assert strength is not None
    assert strength.total_vorp == pytest.approx(110.0)
    assert strength.avg_vorp == pytest.approx(110.0 / 3)
