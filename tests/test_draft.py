"""选秀模拟测试（蛇形 + 蒙特卡洛）。"""

from __future__ import annotations

import pytest

from fantasy_baseball.core.draft import SnakeDraftSimulator
from fantasy_baseball.core.monte_carlo import (
    DraftEngine,
    calculate_availability,
    get_drafter,
)
from fantasy_baseball.core.scoring import ScoringModel


def _full_rankings(fresh_conn, sample_hitters, sample_pitchers):
    """构造完整排名（合并打者投手）。"""
    from fantasy_baseball.db import PlayerRepository
    PlayerRepository(fresh_conn).replace_merged_hitters(sample_hitters)
    PlayerRepository(fresh_conn).replace_merged_pitchers(sample_pitchers)
    return ScoringModel(conn=fresh_conn).calculate_vorp()


def test_snake_draft_basic(fresh_conn, sample_hitters, sample_pitchers):
    rankings = _full_rankings(fresh_conn, sample_hitters, sample_pitchers)
    sim = SnakeDraftSimulator(rankings)
    log = sim.simulate_draft(user_pick=1, strategy="balanced")
    # 联盟12队15轮=180 picks，但只有5个球员，所以最多5 picks
    assert len(log) <= 5
    assert "is_user_pick" in log.columns
    assert "round" in log.columns


def test_snake_draft_invalid_pick(fresh_conn, sample_hitters, sample_pitchers):
    rankings = _full_rankings(fresh_conn, sample_hitters, sample_pitchers)
    sim = SnakeDraftSimulator(rankings)
    with pytest.raises(ValueError, match="顺位"):
        sim.simulate_draft(user_pick=0)


def test_snake_draft_strategies(fresh_conn, sample_hitters, sample_pitchers):
    rankings = _full_rankings(fresh_conn, sample_hitters, sample_pitchers)
    for strategy in ("balanced", "conservative", "aggressive"):
        sim = SnakeDraftSimulator(rankings)
        log = sim.simulate_draft(user_pick=3, strategy=strategy)
        assert len(log) > 0


def test_value_pick_direction(monkeypatch):
    """价值股方向（审计高危项回归）：滑落者标记，提前抢人（reach）不标记。

    旧实现 (adp - total_pick) > 阈值 方向相反，把 reach 标成价值股。
    """
    import pandas as pd

    adp_df = pd.DataFrame({"name": ["X", "Y"], "pos": ["OF", "SS"], "adp": [100.0, 100.0]})
    monkeypatch.setattr(
        "fantasy_baseball.core.draft.ADPCache",
        lambda: type("C", (), {"fetch_adp": lambda self: adp_df, "adp_file": ""})(),
    )
    rankings = pd.DataFrame({"name": ["X", "Y"], "pos": ["OF", "SS"], "vorp": [10.0, 9.0]})
    sim = SnakeDraftSimulator(rankings)

    # ADP=100 的球员在第 115 顺位被选中：滑落 15 检 → 价值股
    assert sim._is_value_pick(115, "X") is True
    # 第 85 顺位抢走 ADP=100 的球员：reach，不是价值股（旧实现会误标）
    assert sim._is_value_pick(85, "Y") is False
    # 无 ADP 数据的球员不标记
    assert sim._is_value_pick(50, "Unknown") is False


def test_calculate_availability_higher_adp_more_available():
    """ADP 越大（顺位越靠后），在靠前顺位可用概率越高。"""
    probs = calculate_availability([10.0, 50.0, 200.0], target_pick=20)
    # ADP=10 在 pick=20 前基本已被选，可用率低
    # ADP=200 在 pick=20 时大概率可用
    assert probs[0] < probs[1] < probs[2]


def test_calculate_availability_unranked_default():
    """ADP >= 999（未排名）默认 0.9 可用率。"""
    probs = calculate_availability([999.0], target_pick=5)
    assert probs[0] == pytest.approx(0.9)


def test_get_drafter_returns_correct_type():
    from fantasy_baseball.core.monte_carlo import (
        ADPFollowerDrafter, BalancedDrafter, PositionalHoarderDrafter,
        StatcastBelieverDrafter, YourStrategyDrafter,
    )
    cfg = {"roster_slots": {"C": 1, "OF": 3}}
    assert isinstance(get_drafter("balanced", cfg), BalancedDrafter)
    assert isinstance(get_drafter("positional", cfg), PositionalHoarderDrafter)
    assert isinstance(get_drafter("statcast", cfg), StatcastBelieverDrafter)
    assert isinstance(get_drafter("adp", cfg), ADPFollowerDrafter)
    assert isinstance(get_drafter("yours", cfg), YourStrategyDrafter)
    # 未知策略降级为 Balanced
    assert isinstance(get_drafter("unknown", cfg), BalancedDrafter)


def test_monte_carlo_engine_availability(fresh_conn, sample_hitters, sample_pitchers):
    rankings = _full_rankings(fresh_conn, sample_hitters, sample_pitchers)
    engine = DraftEngine(rankings)
    avail = engine.analyze_availability(target_pick=10)
    assert "availability_prob" in avail.columns
    assert len(avail) == 5
    # 概率在 [0, 1]
    assert (avail["availability_prob"] >= 0).all()
    assert (avail["availability_prob"] <= 1).all()


def test_monte_carlo_simulate_draft_sgp_pool():
    """回归（审计项）：SGP 池没有 vorp 列，simulate_draft 不再 KeyError。

    输出价值列与 analyze_availability 一致，用 sgp_total 命名。
    """
    import numpy as np
    import pandas as pd
    from fantasy_baseball.core.monte_carlo import DraftEngine

    pool = pd.DataFrame({
        "name": [f"P{i:02d}" for i in range(30)],
        "pos": ["OF"] * 30,
        "sgp_total": np.linspace(10.0, 0.1, 30),
    })
    engine = DraftEngine(pool, method="sgp")
    result = engine.simulate_draft(iterations=50)
    assert "sgp_total" in result.columns
    assert len(result) == 30
    assert result["times_drafted"].sum() <= 50 * 12 * 15
