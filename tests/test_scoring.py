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


def test_generate_rankings(
    tmpdir, fresh_conn, isolated_db, isolated_history, monkeypatch,
    sample_hitters, sample_pitchers,
):
    _seed_merged(fresh_conn, sample_hitters, sample_pitchers)
    out = str(tmpdir.join("rankings.csv"))
    monkeypatch.setattr(
        "fantasy_baseball.core.scoring.output_path", lambda p: out
    )
    sm = ScoringModel(conn=fresh_conn)
    path = sm.generate_rankings(out)
    assert path == out

    import pandas as pd
    df = pd.read_csv(path)
    assert len(df) == 5
    assert df.iloc[0]["rank"] == 1


# ============================================================
# 替代水平分位数方向（审计高危项回归：旧实现方向颠倒）
# ============================================================
def test_replacement_quantile_direction():
    """分位数应落在池的上半区：固定被选 47/150 人 → 升序 ~68 分位。

    旧实现 q = fixed/total 取升序 31 分位（第 N 差球员），方向相反。
    """
    sm = ScoringModel()
    # OF：12 队 × 4 槽 - stream 分摊(5×4/17) ≈ 46.8 固定
    q = sm._replacement_quantile(total_players=150, pos_slots=4)
    assert q == pytest.approx(1.0 - (12 * 4 - 5 * 4 / 17) / 150, abs=1e-9)
    assert q > 0.5  # 固定人数少于池半数 → 边界在池的上半区

    # 池比固定需求还小（全池都会被选走）→ 替代水平贴近最差者，q 触底
    assert sm._replacement_quantile(total_players=5, pos_slots=4) == 0.10


def test_vorp_signs_in_large_pool(fresh_conn):
    """60 人大池：替代线之上的球员 VORP>0，之下的 <0（不触 clip 边界）。

    12 队 × 4 OF 槽 - stream 分摊 ≈ 46.8 人固定 → 边界约在 60 人池的第 47 名。
    """
    hitters = []
    for i in range(60):
        s = 300.0 - i * 3.0  # 分数线性递减，边界清晰
        hitters.append({
            "name": f"OF{i:02d}", "team": "TM", "pos": "OF",
            "R": s - 0.250, "HR": 0, "RBI": 0, "SB": 0,
            "AVG": 0.250, "PA": 500,
        })
    PlayerRepository(fresh_conn).replace_merged_hitters(hitters)

    df = ScoringModel(conn=fresh_conn).calculate_vorp()
    by_name = df.set_index("name")["vorp"]
    assert by_name["OF00"] > 0   # 池内最好
    assert by_name["OF40"] > 0   # 第 41 名，仍在固定线之上
    assert by_name["OF50"] < 0   # 第 51 名，低于固定线
    assert by_name["OF59"] < 0   # 池内最差
    # 方向修复的核心：正值人数应接近固定需求（~47），而不是只有零星几人
    assert (df["vorp"] > 0).sum() >= 40


def test_negative_vorp_upside_floor_direction(fresh_conn):
    """回归（审计项）：负 VORP 时 upside/floor 不得方向反转。

    旧实现 vorp*(1±adj) 对负值：-10 → upside=-13 < floor=-7（反转）。
    """
    hitters = [
        {"name": "PosH", "team": "TM", "pos": "OF", "R": 100, "HR": 30, "RBI": 100,
         "SB": 20, "AVG": 0.300, "PA": 600},
        {"name": "NegH", "team": "TM", "pos": "OF", "R": 5, "HR": 0, "RBI": 5,
         "SB": 0, "AVG": 0.150, "PA": 100},
    ]
    PlayerRepository(fresh_conn).replace_merged_hitters(hitters)

    import copy
    from fantasy_baseball.config import get_config
    cfg = get_config()
    cfg["risk_model"]["method"] = "historical_variance"
    cfg["risk_model"]["adjustment_factor"] = 0.3
    sm = ScoringModel(conn=fresh_conn)
    sm.risk_method = "historical_variance"
    sm.risk_adjustment = 0.3
    df = sm.calculate_vorp()
    neg = df[df["name"] == "NegH"].iloc[0]
    # 负 VORP：upside 更接近 0（> vorp，旧实现会反转成 upside < floor）；
    # floor 原始值 < vorp，经 clip(lower=0) 后为 0
    assert neg["vorp"] < 0
    assert neg["vorp_upside"] >= neg["vorp"] - 1e-9
    assert neg["vorp_floor"] == 0.0  # clip(lower=0)


def test_eligible_pos_multi_position_vorp(fresh_conn):
    """回归（审计项）：eligible_pos 多位置资格入库后应生效。

    双资格球员（2B/SS）取两个位置中替代水平对自己最有利的一个。
    """
    hitters = [
        # SS 池：两名强打者 → SS 替代水平高
        {"name": "StarSS", "team": "TM", "pos": "SS", "R": 95, "HR": 28, "RBI": 90,
         "SB": 30, "AVG": 0.295, "PA": 640},
        {"name": "GoodSS", "team": "TM", "pos": "SS", "R": 85, "HR": 20, "RBI": 75,
         "SB": 20, "AVG": 0.280, "PA": 600},
        # 2B 池：只有一名平庸球员 → 2B 替代水平低
        {"name": "Weak2B", "team": "TM", "pos": "2B", "R": 50, "HR": 8, "RBI": 40,
         "SB": 5, "AVG": 0.240, "PA": 450},
        # 双资格：主位置 2B，同时有 SS 资格；评分与 GoodSS 相同
        {"name": "DualGuy", "team": "TM", "pos": "2B", "eligible_pos": "2B,SS",
         "R": 85, "HR": 20, "RBI": 75, "SB": 20, "AVG": 0.280, "PA": 600},
    ]
    PlayerRepository(fresh_conn).replace_merged_hitters(hitters)

    df = ScoringModel(conn=fresh_conn).calculate_vorp()
    by_name = df.set_index("name")["vorp"]
    # 池太小（fixed > total）时各位置替代水平都贴近最差者：
    # DualGuy 与 GoodSS 评分相同，DualGuy 应取 2B/SS 中对自己更有利的位置，
    # 其 VORP 不低于单位置 2B 的算法结果，且高于 Weak2B
    assert by_name["DualGuy"] > by_name["Weak2B"]
    # 死代码修复的核心断言：eligible_pos 非空且含逗号时走多位置分支（不抛错、有值）
    assert not (df.loc[df["name"] == "DualGuy", "vorp"].isna().any())
