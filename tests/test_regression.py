"""数值回归测试。

用固定输入数据跑 scoring/draft，断言具体数值。
如果算法被悄悄改变（重构、参数调整），这些测试会立刻发现。

参考值由当前代码生成，pytest.approx 容差 1e-4。
"""

from __future__ import annotations

import pytest

from fantasy_baseball.core import ScoringModel, SnakeDraftSimulator
from fantasy_baseball.db import PlayerRepository

# ============================================================
# 固定测试数据（多球员同位置，让替代水平有意义）
# ============================================================
REGRESSION_HITTERS = [
    {"name": "StarOF", "team": "TM", "pos": "OF", "R": 100, "HR": 35, "RBI": 100, "SB": 25, "AVG": 0.300, "OBP": 0.380, "SLG": 0.550, "OPS": 0.930, "PA": 650},
    {"name": "MidOF", "team": "TM", "pos": "OF", "R": 80, "HR": 18, "RBI": 70, "SB": 15, "AVG": 0.270, "OBP": 0.340, "SLG": 0.440, "OPS": 0.780, "PA": 600},
    {"name": "WeakOF", "team": "TM", "pos": "OF", "R": 50, "HR": 8, "RBI": 35, "SB": 5, "AVG": 0.240, "OBP": 0.300, "SLG": 0.360, "OPS": 0.660, "PA": 400},
    {"name": "StarSS", "team": "TM", "pos": "SS", "R": 95, "HR": 28, "RBI": 90, "SB": 30, "AVG": 0.295, "OBP": 0.370, "SLG": 0.520, "OPS": 0.890, "PA": 640},
    {"name": "WeakSS", "team": "TM", "pos": "SS", "R": 55, "HR": 8, "RBI": 40, "SB": 12, "AVG": 0.245, "OBP": 0.310, "SLG": 0.380, "OPS": 0.690, "PA": 480},
    {"name": "Star1B", "team": "TM", "pos": "1B", "R": 85, "HR": 38, "RBI": 105, "SB": 1, "AVG": 0.285, "OBP": 0.370, "SLG": 0.540, "OPS": 0.910, "PA": 630},
    {"name": "Weak1B", "team": "TM", "pos": "1B", "R": 50, "HR": 15, "RBI": 55, "SB": 0, "AVG": 0.250, "OBP": 0.310, "SLG": 0.420, "OPS": 0.730, "PA": 450},
]

REGRESSION_PITCHERS = [
    {"name": "AceSP", "team": "TM", "pos": "SP", "W": 18, "L": 6, "SV": 0, "HOLD": 0, "ERA": 2.50, "WHIP": 0.95, "K_per_9": 11.5, "BB_per_9": 2.0, "IP": 200},
    {"name": "MidSP", "team": "TM", "pos": "SP", "W": 12, "L": 10, "SV": 0, "HOLD": 0, "ERA": 4.00, "WHIP": 1.25, "K_per_9": 8.5, "BB_per_9": 3.0, "IP": 170},
    {"name": "WeakSP", "team": "TM", "pos": "SP", "W": 6, "L": 12, "SV": 0, "HOLD": 0, "ERA": 5.20, "WHIP": 1.45, "K_per_9": 7.0, "BB_per_9": 3.8, "IP": 130},
    {"name": "CloserRP", "team": "TM", "pos": "RP", "W": 4, "L": 3, "SV": 35, "HOLD": 0, "ERA": 3.00, "WHIP": 1.10, "K_per_9": 13.0, "BB_per_9": 3.0, "IP": 60},
    {"name": "SetupRP", "team": "TM", "pos": "RP", "W": 6, "L": 4, "SV": 3, "HOLD": 25, "ERA": 3.40, "WHIP": 1.20, "K_per_9": 10.0, "BB_per_9": 3.2, "IP": 70},
]

# 参考数值（由当前算法生成，容差 1e-2）
# 打者 score = R*1 + HR*1 + RBI*1 + SB*1 + AVG*1
EXPECTED_SCORES = {
    "StarOF": 260.30, "MidOF": 183.27, "WeakOF": 98.24,
    "StarSS": 243.295, "WeakSS": 115.245,
    "Star1B": 229.285, "Weak1B": 120.25,
    "AceSP": 26.05, "MidSP": 15.25, "WeakSP": 6.35,
    "CloserRP": 47.90, "SetupRP": 39.40,
}

EXPECTED_VORPS = {
    "StarOF": 119.545, "StarSS": 96.0375, "Star1B": 81.7763,
    "MidOF": 42.515, "CloserRP": 32.65, "SetupRP": 24.15,
    "AceSP": 10.80, "MidSP": 0.0, "WeakSP": -8.90,
    "Weak1B": -27.2587, "WeakSS": -32.0125, "WeakOF": -42.515,
}

# 打者按位置 25 分位数作替代水平；投手按全体 25 分位数


@pytest.fixture
def seeded_rankings(fresh_conn):
    """填充固定数据并返回排名 DataFrame。"""
    repo = PlayerRepository(fresh_conn)
    repo.replace_merged_hitters(REGRESSION_HITTERS)
    repo.replace_merged_pitchers(REGRESSION_PITCHERS)
    return ScoringModel(conn=fresh_conn).calculate_vorp()


# ============================================================
# 打者评分回归
# ============================================================
class TestHitterScoreRegression:
    def test_star_of_score(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "StarOF"].iloc[0]
        assert row["score"] == pytest.approx(EXPECTED_SCORES["StarOF"], abs=1e-2)

    def test_weak_of_score(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "WeakOF"].iloc[0]
        assert row["score"] == pytest.approx(EXPECTED_SCORES["WeakOF"], abs=1e-2)

    def test_star_1b_score(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "Star1B"].iloc[0]
        assert row["score"] == pytest.approx(EXPECTED_SCORES["Star1B"], abs=1e-2)


# ============================================================
# 投手评分回归
# ============================================================
class TestPitcherScoreRegression:
    def test_ace_sp_score(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "AceSP"].iloc[0]
        # SP 评分 = W*1 + SV*1 + HOLD*1 + ERA*(-1) + WHIP*(-1) + K_per_9*1
        # = 18 + 0 + 0 - 2.5 - 0.95 + 11.5 = 26.05
        assert row["score"] == pytest.approx(EXPECTED_SCORES["AceSP"], abs=1e-2)

    def test_closer_rp_score(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "CloserRP"].iloc[0]
        # = 4 + 35 + 0 - 3.0 - 1.10 + 13.0 = 47.90
        assert row["score"] == pytest.approx(EXPECTED_SCORES["CloserRP"], abs=1e-2)


# ============================================================
# VORP 回归
# ============================================================
class TestVorpRegression:
    def test_star_of_vorp(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "StarOF"].iloc[0]
        assert row["vorp"] == pytest.approx(EXPECTED_VORPS["StarOF"], abs=1e-2)

    def test_star_ss_vorp(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "StarSS"].iloc[0]
        assert row["vorp"] == pytest.approx(EXPECTED_VORPS["StarSS"], abs=1e-2)

    def test_ace_sp_vorp(self, seeded_rankings):
        row = seeded_rankings[seeded_rankings["name"] == "AceSP"].iloc[0]
        assert row["vorp"] == pytest.approx(EXPECTED_VORPS["AceSP"], abs=1e-2)

    def test_mid_sp_vorp_is_zero(self, seeded_rankings):
        """MidSP 是投手 25 分位数替代水平，VORP 应为 0。"""
        row = seeded_rankings[seeded_rankings["name"] == "MidSP"].iloc[0]
        assert row["vorp"] == pytest.approx(0.0, abs=1e-2)

    def test_weak_players_negative_vorp(self, seeded_rankings):
        """弱于替代水平的球员 VORP 为负。"""
        for name in ("WeakOF", "WeakSS", "Weak1B", "WeakSP"):
            row = seeded_rankings[seeded_rankings["name"] == name].iloc[0]
            assert row["vorp"] < 0, f"{name} 的 VORP 应为负，实际 {row['vorp']}"


# ============================================================
# 风险评分回归
# ============================================================
class TestRiskScoreRegression:
    def test_floor_non_negative(self, seeded_rankings):
        """vorp_floor 不应为负（clip lower=0）。"""
        assert (seeded_rankings["vorp_floor"] >= 0).all()

    def test_upside_ge_vorp(self, seeded_rankings):
        """z_score 法：upside 应 >= vorp。"""
        for _, r in seeded_rankings.iterrows():
            assert r["vorp_upside"] >= r["vorp"] - 1e-6

    def test_upside_floor_symmetric(self, seeded_rankings):
        """z_score 法：upside - vorp == vorp - floor（调整前后对称）。"""
        hitters = seeded_rankings[seeded_rankings["player_type"] == "hitter"]
        for _, r in hitters.iterrows():
            if r["vorp_floor"] > 0:  # 只检查未被 clip 的
                upside_diff = r["vorp_upside"] - r["vorp"]
                floor_diff = r["vorp"] - r["vorp_floor"]
                assert upside_diff == pytest.approx(floor_diff, abs=1e-4)


# ============================================================
# 排名回归
# ============================================================
class TestRankRegression:
    def test_rank_order_matches_vorp_desc(self, seeded_rankings):
        """排名顺序应与 VORP 降序一致。"""
        df = seeded_rankings.sort_values("rank")
        assert df["rank"].tolist() == list(range(1, len(df) + 1))
        vorps = df["vorp"].tolist()
        assert vorps == sorted(vorps, reverse=True)

    def test_top1_is_star_of(self, seeded_rankings):
        """VORP 第一应是 StarOF。"""
        top = seeded_rankings.iloc[0]
        assert top["name"] == "StarOF"
        assert top["rank"] == 1

    def test_total_player_count(self, seeded_rankings):
        assert len(seeded_rankings) == 12  # 7 打者 + 5 投手


# ============================================================
# 选秀模拟回归
# ============================================================
class TestDraftRegression:
    def test_draft_first_pick_is_top_vorp(self, seeded_rankings):
        """balanced 策略第1顺位首选应是 VORP 最高的球员。"""
        sim = SnakeDraftSimulator(seeded_rankings)
        log = sim.simulate_draft(user_pick=1, strategy="balanced")
        first_pick = log.iloc[0]
        top_vorp = seeded_rankings.iloc[0]["name"]
        assert first_pick["name"] == top_vorp

    def test_draft_total_picks(self, seeded_rankings):
        """选秀总选择数不应超过球员总数。"""
        sim = SnakeDraftSimulator(seeded_rankings)
        log = sim.simulate_draft(user_pick=3, strategy="balanced")
        assert len(log) <= len(seeded_rankings)

    def test_no_player_drafted_twice(self, seeded_rankings):
        """同一球员不应被选两次。"""
        sim = SnakeDraftSimulator(seeded_rankings)
        log = sim.simulate_draft(user_pick=2, strategy="aggressive")
        names = log["name"].tolist()
        assert len(names) == len(set(names)), "有球员被重复选择"
