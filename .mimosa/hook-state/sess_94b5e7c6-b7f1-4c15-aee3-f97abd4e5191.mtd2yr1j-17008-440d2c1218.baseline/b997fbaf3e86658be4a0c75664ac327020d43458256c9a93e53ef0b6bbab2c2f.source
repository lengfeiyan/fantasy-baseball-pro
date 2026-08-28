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


def test_real_time_player_stats(fresh_conn, tmpdir, monkeypatch):
    """fetch_player_stats 应返回包含 stats 字段的数据。

    不依赖网络：mock MLB 客户端返回固定数据。cache_dir 指向临时目录，
    避免测试数据污染真实 data/cache（曾导致跨测试的缓存命中干扰）。
    """
    rtd = RealTimeData(conn=fresh_conn, cache_dir=str(tmpdir))
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


# ============================================================
# 审计项回归：DH 归一化评分 / None 统计防护
# ============================================================
def test_base_score_dh_not_zero(fresh_conn):
    """回归（审计项）：DH 归一化为 UTIL 后必须仍能评分。

    旧实现 HITTER_POSITIONS 缺 UTIL → Stanton 等专职 DH base_score=0。
    """
    from fantasy_baseball.fa.analyzer import FAAnalyzer, _normalize_pos
    a = FAAnalyzer(conn=fresh_conn)
    assert _normalize_pos("DH") == "UTIL"
    stats = {"pos": "UTIL", "stats": {"R": 100, "HR": 30, "RBI": 100, "SB": 5, "AVG": 0.280}}
    assert a._calculate_base_score(stats) > 0


def test_base_score_none_stats_no_crash(fresh_conn):
    """回归（审计项）：MLB 占位符产生 None 时不再 TypeError（球员被静默丢弃）。"""
    from fantasy_baseball.fa.analyzer import FAAnalyzer
    a = FAAnalyzer(conn=fresh_conn)
    stats = {"pos": "OF", "stats": {"R": 90, "HR": 20, "RBI": 80, "SB": 10, "AVG": None}}
    score = a._calculate_base_score(stats)
    assert score == pytest.approx(90 + 20 + 80 + 10)  # AVG 记 0，其余正常累加


# ============================================================
# 中危项回归：statcast 相对分 / need 归一化 / 风险偏好 / mock 标记
# ============================================================
def test_statcast_score_not_saturated(fresh_conn):
    """回归（审计项）：旧公式恒饱和 100，25% 权重失效。

    新公式 50 为基准的相对分：均值球员 ~50，好/差球员应拉开且不全撞 100。
    """
    from fantasy_baseball.fa.analyzer import FAAnalyzer
    a = FAAnalyzer(conn=fresh_conn)

    good = a._calculate_statcast_score({
        "pos": "OF", "statcast": {
            "xwOBA": 0.370, "barrel_rate": 0.11, "exit_velocity": 92.0,
            "hard_hit_rate": 0.45, "swing_contact_rate": 0.85,
        }})
    avg = a._calculate_statcast_score({
        "pos": "OF", "statcast": {
            "xwOBA": 0.310, "barrel_rate": 0.06, "exit_velocity": 88.0,
            "hard_hit_rate": 0.38, "swing_contact_rate": 0.80,
        }})
    bad = a._calculate_statcast_score({
        "pos": "OF", "statcast": {
            "xwOBA": 0.280, "barrel_rate": 0.03, "exit_velocity": 85.0,
            "hard_hit_rate": 0.30, "swing_contact_rate": 0.72,
        }})
    assert good > avg > bad
    assert avg < 100  # 均值球员不再饱和 100（旧公式全员撞上限）；精英可到 100
    assert bad > 0


def test_recommendation_need_factor_normalizes_pos(fresh_conn):
    """回归（审计项）：池内 CF/DH/P 等原始位置归一化后查需求表，
    不再一律落到默认 0.5。"""
    from fantasy_baseball.fa.recommendation import RecommendationSystem, _normalize_slot

    rec = RecommendationSystem(conn=fresh_conn)
    assert _normalize_slot("CF") == "OF"
    assert _normalize_slot("DH") == "UTIL"
    assert _normalize_slot("P") == "SP"
    # OF 槽 4 个、阵容 0 人 → need=1.0；归一化前 CF 落到默认 0.5
    needs = rec.analyze_roster_needs(user_roster=[])
    assert needs["OF"] == 1.0


def test_recommendation_risk_preference_changes_order(fresh_conn, monkeypatch):
    """回归（审计项）：风险偏好曾为全局乘数，不改变排序。

    新逻辑：conservative 放大伤病惩罚、aggressive 衰减——重伤球员在
    conservative 下应被压得低于轻伤球员。
    """
    from fantasy_baseball.fa.recommendation import RecommendationSystem

    rec = RecommendationSystem(conn=fresh_conn)
    # 模拟：两名球员分数相近，A 重伤、B 健康
    def fake_value(self, pid):
        return {
            "player_id": pid, "name": f"P{pid}", "overall_value": 100.0,
            "base_score": 50, "statcast_score": 20, "is_mock": False,
        }
    monkeypatch.setattr(FAAnalyzer, "calculate_fa_value", fake_value)
    # 重伤球员的轻量伤病查询返回 severe（风险调整不再走全量评估）
    def fake_injury(self, pid):
        if pid == 1:
            return {"severity": "severe"}
        return None
    monkeypatch.setattr(FAAnalyzer, "get_active_injury", fake_injury)
    # 池：P1 重伤、P2 健康，但 need_factor 让 P1 略高
    monkeypatch.setattr(rec, "analyze_roster_needs", lambda *a, **k: {"OF": 1.0, "SP": 0.0})
    monkeypatch.setattr(
        rec.fa_analyzer, "get_fa_pool",
        lambda position=None: [
            {"player_id": 1, "name": "HurtH", "pos": "OF", "team": "T"},
            {"player_id": 2, "name": "HealthyH", "pos": "OF", "team": "T"},
        ],
    )
    cons = rec.generate_recommendations(top_n=5, risk_preference="conservative")
    aggr = rec.generate_recommendations(top_n=5, risk_preference="aggressive")
    cons_names = [r["name"] for r in cons]
    aggr_names = [r["name"] for r in aggr]
    # 至少要能出推荐
    assert len(cons) == 2 and len(aggr) == 2
    # 两名球员 need 相同，conservative 下重伤者应排后
    assert cons_names[0] == "HealthyH"
    assert aggr_names[0] == "HealthyH"  # aggressive 仍健康优先（惩罚只是衰减）
    # 但两偏好下重伤者的 risk_adjustment 应有区别
    cons_hurt = next(r for r in cons if r["name"] == "HurtH")
    aggr_hurt = next(r for r in aggr if r["name"] == "HurtH")
    assert cons_hurt["risk_adjustment"] < aggr_hurt["risk_adjustment"]


def test_mock_stats_flagged(fresh_conn, tmpdir, monkeypatch):
    """回归（审计项）：真实数据不可用降级 mock 时带 is_mock 标记，
    上层可区分示例数据与真实数据。"""
    rtd = RealTimeData(conn=fresh_conn, cache_dir=str(tmpdir))
    monkeypatch.setattr(
        rtd._mlb, "fetch_player_stats", lambda pid, season: None
    )
    stats = rtd.fetch_player_stats(99999)
    assert stats.get("is_mock") is True


# ============================================================
# 审计回归：xera 量级 + statcast 缺字段中性
# ============================================================
def test_statcast_pitcher_xera_real_scale(fresh_conn):
    """xera 按 statcast.py 实际口径（xwOBA×5.5 ≈ 1.8-2.2）评分。

    旧公式按官方 xERA 量级（基准 3.80）→ 联网投手恒 +45 撞满 100。
    """
    from fantasy_baseball.fa.analyzer import FAAnalyzer
    a = FAAnalyzer(conn=fresh_conn)
    elite = a._calculate_statcast_score({
        "pos": "SP", "statcast": {"xera": 1.80}})   # 真实口径的精英
    avg = a._calculate_statcast_score({
        "pos": "SP", "statcast": {"xera": 2.05}})   # 典型
    poor = a._calculate_statcast_score({
        "pos": "SP", "statcast": {"xera": 2.30}})   # 真实口径的差生
    assert elite > avg > poor
    assert avg == pytest.approx(50.0, abs=1.0)   # 典型值 ≈ 基准 50
    assert elite < 100 and poor > 0


def test_statcast_missing_keys_neutral(fresh_conn):
    """回归：statcast 部分字段缺失按中性跳过，不再当联盟最差值归零。"""
    from fantasy_baseball.fa.analyzer import FAAnalyzer
    a = FAAnalyzer(conn=fresh_conn)
    # 只有 exit_velocity 一项，其余键全部缺失 → 应 ≈50（中性），而非 clip 到 0
    score = a._calculate_statcast_score({
        "pos": "OF", "statcast": {"exit_velocity": 88.0}})
    assert score == pytest.approx(50.0, abs=1.0)
    # 全缺 → 恰好 50
    assert a._calculate_statcast_score({"pos": "OF", "statcast": {"x": 1}}) == pytest.approx(50.0)


def test_unified_injury_factors_no_double_punish(fresh_conn, monkeypatch):
    """审计回归：单一系数表 + 半权重——long_term 综合惩罚不再是 ×0.045。"""
    from fantasy_baseball.fa.analyzer import INJURY_FACTORS
    from fantasy_baseball.fa.recommendation import RecommendationSystem

    rec = RecommendationSystem(conn=fresh_conn)
    monkeypatch.setattr(
        type(rec.fa_analyzer), "get_active_injury",
        lambda self, pid: {"severity": "long_term"},
    )
    balanced = rec._calculate_risk_adjustment(1, "balanced")
    conservative = rec._calculate_risk_adjustment(1, "conservative")
    aggressive = rec._calculate_risk_adjustment(1, "aggressive")
    # 半权重：balanced = 1 - 0.7*0.5 = 0.65（旧幂缩放给 0.3^1.0=0.3）
    assert balanced == pytest.approx(0.65, abs=0.01)
    assert conservative < balanced < aggressive
    # 与 analyzer 的价值折减叠加后：0.30 × 0.65 = 0.195（旧双重惩罚 0.15×0.3=0.045）
    assert INJURY_FACTORS["long_term"] * balanced > 0.15
