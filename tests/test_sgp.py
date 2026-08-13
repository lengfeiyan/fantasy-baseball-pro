"""SGP 评分模型测试。

与 VORP 回归测试使用相同的固定球员数据（补了 SGP 需要的 AB/H/BB/K/ER 等列），
断言具体 SGP 数值。
"""

from __future__ import annotations

import pytest

from fantasy_baseball.core.sgp import SGPModel
from fantasy_baseball.db import PlayerRepository

# 固定测试数据（含 SGP 需要的额外列）
SGP_HITTERS = [
    {"name": "StarOF", "team": "TM", "pos": "OF", "R": 100, "HR": 35, "RBI": 100, "SB": 25,
     "AVG": 0.300, "OBP": 0.380, "SLG": 0.550, "OPS": 0.930, "PA": 650,
     "AB": 580, "H": 174, "BB": 60, "SO": 120},
    {"name": "MidOF", "team": "TM", "pos": "OF", "R": 80, "HR": 18, "RBI": 70, "SB": 15,
     "AVG": 0.270, "OBP": 0.340, "SLG": 0.440, "OPS": 0.780, "PA": 600,
     "AB": 540, "H": 146, "BB": 50, "SO": 110},
    {"name": "WeakOF", "team": "TM", "pos": "OF", "R": 50, "HR": 8, "RBI": 35, "SB": 5,
     "AVG": 0.240, "OBP": 0.300, "SLG": 0.360, "OPS": 0.660, "PA": 400,
     "AB": 380, "H": 91, "BB": 18, "SO": 90},
    {"name": "StarSS", "team": "TM", "pos": "SS", "R": 95, "HR": 28, "RBI": 90, "SB": 30,
     "AVG": 0.295, "OBP": 0.370, "SLG": 0.520, "OPS": 0.890, "PA": 640,
     "AB": 570, "H": 168, "BB": 55, "SO": 100},
    {"name": "Star1B", "team": "TM", "pos": "1B", "R": 85, "HR": 38, "RBI": 105, "SB": 1,
     "AVG": 0.285, "OBP": 0.370, "SLG": 0.540, "OPS": 0.910, "PA": 630,
     "AB": 560, "H": 160, "BB": 65, "SO": 130},
]

SGP_PITCHERS = [
    {"name": "AceSP", "team": "TM", "pos": "SP", "W": 18, "L": 6, "SV": 0, "HOLD": 0,
     "ERA": 2.50, "WHIP": 0.95, "K_per_9": 11.5, "BB_per_9": 2.0, "IP": 200,
     "K": 256, "ER": 56, "H_allow": 160, "BB_allow": 44},
    {"name": "MidSP", "team": "TM", "pos": "SP", "W": 12, "L": 10, "SV": 0, "HOLD": 0,
     "ERA": 4.00, "WHIP": 1.25, "K_per_9": 8.5, "BB_per_9": 3.0, "IP": 170,
     "K": 161, "ER": 76, "H_allow": 170, "BB_allow": 57},
    {"name": "CloserRP", "team": "TM", "pos": "RP", "W": 4, "L": 3, "SV": 35, "HOLD": 0,
     "ERA": 3.00, "WHIP": 1.10, "K_per_9": 13.0, "BB_per_9": 3.0, "IP": 60,
     "K": 87, "ER": 20, "H_allow": 55, "BB_allow": 20},
]


@pytest.fixture
def seeded_sgp(fresh_conn):
    """填充 SGP 固定数据并返回排名。"""
    repo = PlayerRepository(fresh_conn)
    repo.replace_merged_hitters(SGP_HITTERS)
    repo.replace_merged_pitchers(SGP_PITCHERS)
    return SGPModel(conn=fresh_conn).calculate_sgp()


# ============================================================
# 打者 SGP 回归
# ============================================================
class TestHitterSGP:
    def test_star_of_total(self, seeded_sgp):
        row = seeded_sgp[seeded_sgp["name"] == "StarOF"].iloc[0]
        assert row["sgp_total"] == pytest.approx(11.13, abs=0.5)

    def test_hr_sgp(self, seeded_sgp):
        """35 HR / 10.4 ≈ 3.37。"""
        row = seeded_sgp[seeded_sgp["name"] == "StarOF"].iloc[0]
        assert row["sgp_HR"] == pytest.approx(35 / 10.4, abs=0.01)

    def test_avg_sgp_positive(self, seeded_sgp):
        """高 AVG 的球员 sgp_AVG 应为正。"""
        row = seeded_sgp[seeded_sgp["name"] == "StarOF"].iloc[0]
        assert row["sgp_AVG"] > 0  # .300 AVG 拉高团队均值

    def test_avg_sgp_negative_for_low_avg(self, seeded_sgp):
        """低 AVG 的球员 sgp_AVG 应为负（拉低团队均值）。"""
        row = seeded_sgp[seeded_sgp["name"] == "WeakOF"].iloc[0]
        assert row["sgp_AVG"] < 0


# ============================================================
# 投手 SGP 回归
# ============================================================
class TestPitcherSGP:
    def test_ace_sp_total(self, seeded_sgp):
        row = seeded_sgp[seeded_sgp["name"] == "AceSP"].iloc[0]
        assert row["sgp_total"] == pytest.approx(12.33, abs=0.5)

    def test_k_sgp(self, seeded_sgp):
        """256 K / 39.3 ≈ 6.51。"""
        row = seeded_sgp[seeded_sgp["name"] == "AceSP"].iloc[0]
        assert row["sgp_K"] == pytest.approx(256 / 39.3, abs=0.01)

    def test_era_sgp_positive_for_low_era(self, seeded_sgp):
        """ERA 2.50 远低于团队基准 3.59，sgp_ERA 应为正（分母为负，差值为负，负/负=正）。"""
        row = seeded_sgp[seeded_sgp["name"] == "AceSP"].iloc[0]
        assert row["sgp_ERA"] > 0

    def test_closer_sv_sgp(self, seeded_sgp):
        """35 SV / 9.95 ≈ 3.52。"""
        row = seeded_sgp[seeded_sgp["name"] == "CloserRP"].iloc[0]
        assert row["sgp_SV"] == pytest.approx(35 / 9.95, abs=0.01)


# ============================================================
# 排名回归
# ============================================================
class TestSGPRanking:
    def test_rank_order(self, seeded_sgp):
        """排名顺序应与 sgp_total 降序一致。"""
        df = seeded_sgp.sort_values("sgp_rank")
        assert df["sgp_rank"].tolist() == list(range(1, len(df) + 1))
        totals = df["sgp_total"].tolist()
        assert totals == sorted(totals, reverse=True)

    def test_ace_sp_rank1(self, seeded_sgp):
        """AceSP 的 SGP 应最高（投手贡献分散在 5 类，先发投手局数多有优势）。"""
        assert seeded_sgp.iloc[0]["name"] == "AceSP"

    def test_replacement_adjusted(self, seeded_sgp):
        """最后一个球员的 sgp_total 应 ≈ 0（替代水平调整）。"""
        last = seeded_sgp.iloc[-1]
        assert last["sgp_total"] == pytest.approx(0.0, abs=1.0)

    def test_total_count(self, seeded_sgp):
        assert len(seeded_sgp) == 8  # 5 打者 + 3 投手


# ============================================================
# SGP vs VORP 差异验证
# ============================================================
class TestSGPvsVORP:
    def test_sgp_has_avg_contribution(self, seeded_sgp):
        """SGP 里 AVG 应有实际贡献（不像 VORP 里 AVG≈0）。"""
        star = seeded_sgp[seeded_sgp["name"] == "StarOF"].iloc[0]
        # sgp_AVG 应大于 0.5（.300 AVG 有实质贡献）
        assert abs(star["sgp_AVG"]) > 0.5

    def test_sgp_columns_exist(self, seeded_sgp):
        """SGP 排名应含各类别分项。"""
        for col in ["sgp_R", "sgp_HR", "sgp_RBI", "sgp_SB", "sgp_AVG"]:
            assert col in seeded_sgp.columns
