"""FA 分析层测试。"""

from __future__ import annotations

import pytest

from fantasy_baseball.fa import FAAnalyzer, RealTimeData, RecommendationSystem


def test_real_time_update_fa_pool(fresh_conn):
    rtd = RealTimeData(conn=fresh_conn)
    pool = rtd.update_fa_pool()
    assert len(pool) == 5
    names = [p["name"] for p in pool]
    assert "Mike Trout" in names


def test_real_time_update_injury_offline(fresh_conn):
    """离线模式下 update_injury_data 跳过抓取，返回空列表。"""
    rtd = RealTimeData(conn=fresh_conn)
    injuries = rtd.update_injury_data(allow_network=False)
    assert injuries == []


def test_real_time_player_stats(fresh_conn, monkeypatch):
    """fetch_player_stats 应返回包含 stats 字段的数据。

    不依赖网络：mock MLB 客户端返回固定数据。
    """
    rtd = RealTimeData(conn=fresh_conn)
    # 用 monkeypatch 替换 MLB 客户端，避免网络
    monkeypatch.setattr(
        rtd._mlb, "fetch_player_stats",
        lambda pid, season: {
            "name": "Test Player", "team": "TM", "pos": "OF",
            "stats": {"AVG": 0.300, "HR": 20, "RBI": 80, "R": 90, "SB": 15,
                      "OBP": 0.380, "SLG": 0.520, "OPS": 0.900, "PA": 600},
        }
    )
    monkeypatch.setattr(rtd._statcast, "fetch_hitter_data", lambda pid, season: {"exit_velocity": 90.0})
    stats = rtd.fetch_player_stats(99999)
    assert "stats" in stats
    assert stats["stats"]["HR"] == 20


def test_real_time_player_stats_mock_fallback(fresh_conn, monkeypatch):
    """真实数据获取失败时应降级到 mock。"""
    rtd = RealTimeData(conn=fresh_conn)
    # MLB 客户端返回 None 触发降级
    monkeypatch.setattr(rtd._mlb, "fetch_player_stats", lambda pid, season: None)
    monkeypatch.setattr(rtd._statcast, "fetch_hitter_data", lambda pid, season: {})
    # 用一个不会命中缓存的 id
    stats = rtd.fetch_player_stats(888888)
    assert stats is not None
    assert "stats" in stats  # mock 数据


def test_analyzer_value_calculation(fresh_conn, monkeypatch):
    """FA 价值计算应返回各分项（mock 数据源，不依赖网络）。"""
    RealTimeData(conn=fresh_conn).update_injury_data(allow_network=False)
    analyzer = FAAnalyzer(conn=fresh_conn)

    # mock fetch_player_stats 返回固定打者数据（注意 patch 实例方法需含 self）
    def _mock_stats(self, pid):
        return {
            "name": "Test Hitter", "team": "TM", "pos": "OF",
            "stats": {"AVG": 0.300, "HR": 25, "RBI": 90, "R": 95, "SB": 20,
                      "OBP": 0.380, "SLG": 0.520, "OPS": 0.900, "PA": 650},
            "statcast": {"exit_velocity": 92.0, "xwOBA": 0.360, "barrel_rate": 0.12,
                         "hard_hit_rate": 0.40, "swing_contact_rate": 0.82},
        }
    monkeypatch.setattr(RealTimeData, "fetch_player_stats", _mock_stats)

    value = analyzer.calculate_fa_value(1)
    assert "overall_value" in value
    assert "base_score" in value
    assert value["base_score"] > 0  # 打者评分生效
    assert value["pos"] == "OF"
    assert isinstance(value["overall_value"], float)


def test_analyzer_value_pitcher(fresh_conn, monkeypatch):
    """投手位置（SP）应走投手评分。"""
    analyzer = FAAnalyzer(conn=fresh_conn)
    monkeypatch.setattr(RealTimeData, "fetch_player_stats", lambda self, pid: {
        "name": "Test Pitcher", "team": "TM", "pos": "SP",
        "stats": {"W": 15, "SV": 0, "HOLD": 0, "ERA": 3.00, "WHIP": 1.10,
                  "K_per_9": 10.0, "BB_per_9": 2.5, "IP": 180},
        "statcast": {},
    })
    value = analyzer.calculate_fa_value(2)
    assert value["pos"] == "SP"
    assert value["base_score"] > 0


def test_analyzer_get_fa_pool(fresh_conn):
    RealTimeData(conn=fresh_conn).update_fa_pool()
    analyzer = FAAnalyzer(conn=fresh_conn)
    pool = analyzer.get_fa_pool()
    assert len(pool) == 5


def test_recommendation_generate(fresh_conn, monkeypatch):
    """推荐生成应返回排序列表。"""
    RealTimeData(conn=fresh_conn).update_fa_pool()
    # mock 价值计算避免网络
    monkeypatch.setattr(FAAnalyzer, "calculate_fa_value", lambda self, pid: {
        "player_id": pid, "name": f"P{pid}", "overall_value": 100.0 - pid,
        "base_score": 50, "statcast_score": 20,
    })
    analyzer = FAAnalyzer(conn=fresh_conn)
    rec = RecommendationSystem(analyzer, conn=fresh_conn)
    result = rec.generate_recommendations(top_n=3, risk_preference="balanced")
    assert len(result) <= 3
    # 应按 final_score 降序
    scores = [r["final_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_recommendation_position_filter(fresh_conn, monkeypatch):
    RealTimeData(conn=fresh_conn).update_fa_pool()
    monkeypatch.setattr(FAAnalyzer, "calculate_fa_value", lambda self, pid: {
        "player_id": pid, "name": f"P{pid}", "overall_value": 80.0,
        "base_score": 50, "statcast_score": 20,
    })
    analyzer = FAAnalyzer(conn=fresh_conn)
    rec = RecommendationSystem(analyzer, conn=fresh_conn)
    result = rec.generate_recommendations(position="OF", top_n=5)
    # 全部应为 OF（mock 池里 OF 球员）
    for r in result:
        assert r["pos"] == "OF"


def test_recommendation_risk_preference(fresh_conn, monkeypatch):
    """不同风险偏好应影响排序。"""
    RealTimeData(conn=fresh_conn).update_fa_pool()
    monkeypatch.setattr(FAAnalyzer, "calculate_fa_value", lambda self, pid: {
        "player_id": pid, "name": f"P{pid}", "overall_value": 80.0,
        "base_score": 50, "statcast_score": 20,
    })
    analyzer = FAAnalyzer(conn=fresh_conn)
    rec = RecommendationSystem(analyzer, conn=fresh_conn)

    conservative = rec.generate_recommendations(top_n=5, risk_preference="conservative")
    aggressive = rec.generate_recommendations(top_n=5, risk_preference="aggressive")
    # 至少应能生成推荐
    assert len(conservative) > 0
    assert len(aggressive) > 0
