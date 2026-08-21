"""数据统一入库管道测试。

设计：DB 为唯一当前数据源，CSV 降级为历史备份（时间戳文件）+ 最近一份
同名文件（兼容旧读取端）。本文件覆盖四条管道的双写与读取优先级。
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from fantasy_baseball.db import (
    AdpRepository,
    DraftLogRepository,
    PlayerRepository,
    RankingsRepository,
    RecommendationRepository,
)


# ============================================================
# 仓储层语义
# ============================================================
def test_adp_repository_snapshot_semantics(fresh_conn):
    """ADP 快照：整体替换（永远只有一批）。"""
    repo = AdpRepository(fresh_conn)
    assert repo.replace_all([{"name": "A", "pos": "OF", "adp": 10.0}]) == 1
    assert repo.latest_fetch_time() is not None
    repo.replace_all([{"name": "B", "pos": "SS", "adp": 20.0}])
    assert repo.count() == 1
    assert repo.get_all().iloc[0]["name"] == "B"


def test_rankings_repository_method_isolation(fresh_conn):
    """排名快照：按 method 替换，另一 method 不受影响。"""
    repo = RankingsRepository(fresh_conn)
    repo.replace_method("vorp", 2026, [{"rank": 1, "name": "A", "vorp": 9.0}])
    repo.replace_method("sgp", 2026, [{"rank": 1, "name": "B", "sgp_total": 5.0}])
    assert repo.get_latest("vorp").iloc[0]["name"] == "A"
    repo.replace_method("vorp", 2026, [{"rank": 1, "name": "C", "vorp": 8.0}])
    assert repo.get_latest("vorp").iloc[0]["name"] == "C"
    assert repo.get_latest("sgp").iloc[0]["name"] == "B"


def test_draft_log_repository_sessions(fresh_conn):
    """选秀日志会话：追加、查最新、同会话幂等重写。"""
    repo = DraftLogRepository(fresh_conn)
    repo.save_session("s1", [{"round": 1, "pick": 1, "team": 1, "name": "X", "pos": "OF"}],
                      user_pick=1)
    repo.save_session("s2", [{"round": 1, "pick": 1, "team": 2, "name": "Y", "pos": "SS"}],
                      user_pick=2)
    assert repo.count() == 2
    assert repo.latest_session_id() == "s2"
    # 同会话重写幂等（不重复追加）
    repo.save_session("s2", [{"round": 1, "pick": 2, "team": 2, "name": "Z", "pos": "OF"}],
                      user_pick=2)
    assert repo.count() == 2
    assert repo.get_session("s2").iloc[0]["name"] == "Z"


def test_recommendation_repository_sessions(fresh_conn):
    repo = RecommendationRepository(fresh_conn)
    repo.save_session("r1", [{"player_id": 1, "name": "A", "final_score": 80.0}])
    assert repo.latest_session_id() == "r1"
    df = repo.get_session("r1")
    assert df.iloc[0]["final_score"] == 80.0


# ============================================================
# 排名管道双写
# ============================================================
def test_vorp_rankings_dual_write(
    fresh_conn, isolated_db, isolated_history, tmpdir, monkeypatch,
    sample_hitters, sample_pitchers,
):
    PlayerRepository(fresh_conn).replace_merged_hitters(sample_hitters)
    PlayerRepository(fresh_conn).replace_merged_pitchers(sample_pitchers)

    out = str(tmpdir.join("rankings.csv"))
    monkeypatch.setattr("fantasy_baseball.core.scoring.output_path", lambda p: out)

    from fantasy_baseball.core.scoring import ScoringModel

    path = ScoringModel(conn=fresh_conn).generate_rankings(out)
    assert path == out and os.path.exists(out)

    db_df = RankingsRepository(fresh_conn).get_latest("vorp")
    csv_df = pd.read_csv(out)
    assert len(db_df) == len(csv_df)
    assert db_df.iloc[0]["name"] == csv_df.iloc[0]["name"]
    # 时间戳备份已写入（重定向到临时目录）
    assert len(isolated_history) == 1 and os.path.exists(isolated_history[0])


def test_sgp_rankings_dual_write(
    fresh_conn, isolated_db, isolated_history, tmpdir, monkeypatch,
    sample_hitters, sample_pitchers,
):
    from fantasy_baseball.core.sgp import SGPModel

    PlayerRepository(fresh_conn).replace_merged_hitters([
        {**h, "AB": 550, "H": 150} for h in sample_hitters
    ])
    PlayerRepository(fresh_conn).replace_merged_pitchers(sample_pitchers)

    out = str(tmpdir.join("sgp.csv"))
    monkeypatch.setattr("fantasy_baseball.core.sgp.output_path", lambda p: out)
    path = SGPModel(conn=fresh_conn).generate_rankings(out)
    assert os.path.exists(path)

    db_df = RankingsRepository(fresh_conn).get_latest("sgp")
    assert not db_df.empty
    # sgp_rank 在 DB 中统一映射为 rank 列
    assert "rank" in db_df.columns


# ============================================================
# 选秀日志管道双写
# ============================================================
def test_simulate_and_save_dual_write(
    fresh_conn, isolated_db, isolated_history, tmpdir, monkeypatch,
    sample_hitters, sample_pitchers,
):
    from fantasy_baseball.core.draft import SnakeDraftSimulator
    from fantasy_baseball.core.scoring import ScoringModel

    PlayerRepository(fresh_conn).replace_merged_hitters(sample_hitters)
    PlayerRepository(fresh_conn).replace_merged_pitchers(sample_pitchers)
    rankings = ScoringModel(conn=fresh_conn).calculate_vorp()

    out = str(tmpdir.join("draft_log.csv"))
    monkeypatch.setattr("fantasy_baseball.core.draft.output_path", lambda p: out)

    sim = SnakeDraftSimulator(rankings)
    log = sim.simulate_draft(user_pick=1, strategy="balanced")
    path = sim.simulate_and_save(user_pick=1, strategy="balanced", log_df=log)
    assert os.path.exists(path)

    repo = DraftLogRepository(fresh_conn)
    assert repo.count() == len(log)
    latest = repo.latest_session()
    assert len(latest) == len(log)
    # 会话元数据
    assert latest.iloc[0]["method"] == "vorp"
    assert latest.iloc[0]["strategy"] == "balanced"
    assert latest.iloc[0]["user_pick"] == 1
    # 时间戳备份
    assert isolated_history and os.path.exists(isolated_history[0])


# ============================================================
# FA 推荐导出双写
# ============================================================
def test_export_recommendations_dual_write(
    fresh_conn, isolated_db, isolated_history, tmpdir, monkeypatch,
):
    from fantasy_baseball.fa.recommendation import RecommendationSystem

    out = str(tmpdir.join("fa.csv"))
    monkeypatch.setattr(
        "fantasy_baseball.fa.recommendation.output_path", lambda p: out
    )
    recs = [{
        "player_id": 1, "name": "A", "team": "T", "pos": "OF",
        "final_score": 90.0,
        "value": {"overall_value": 80.0, "base_score": 50.0, "statcast_score": 20.0},
        "need_factor": 0.5, "risk_adjustment": 0.9, "is_mock": False,
    }]
    rec = RecommendationSystem(conn=fresh_conn)
    path = rec.export_recommendations(
        recs, "fa.csv", method="sgp", risk_preference="aggressive"
    )
    assert os.path.exists(path)

    repo = RecommendationRepository(fresh_conn)
    df = repo.get_session(repo.latest_session_id())
    assert df.iloc[0]["name"] == "A"
    assert df.iloc[0]["method"] == "sgp"
    assert df.iloc[0]["risk_preference"] == "aggressive"
    assert df.iloc[0]["is_mock"] == 0


# ============================================================
# ADP 管道：DB 优先级
# ============================================================
def test_adp_db_priority_over_csv(fresh_conn, isolated_db):
    """DB 有未过期快照时优先于本地 CSV（根目录 adp.csv 真实存在也不影响）。"""
    from fantasy_baseball.core.adp import ADPCache

    AdpRepository(fresh_conn).replace_all([{"name": "DBRow", "pos": "OF", "adp": 12.0}])
    cache = ADPCache()  # adp_file 未指定 → use_db=True
    df = cache.fetch_adp(allow_network=False)
    assert df.iloc[0]["name"] == "DBRow"


def test_adp_fetch_writes_db_and_backup(
    fresh_conn, isolated_db, isolated_history, monkeypatch,
):
    from fantasy_baseball.core import adp as adp_mod
    from fantasy_baseball.core.adp import ADPCache

    monkeypatch.setattr(
        adp_mod, "fetch_real_adp",
        lambda: pd.DataFrame({"name": ["NetRow"], "pos": ["SS"], "adp": [5.0]}),
    )
    cache = ADPCache()
    df = cache.fetch_adp(force=True)
    assert df.iloc[0]["name"] == "NetRow"
    # DB 已更新
    assert AdpRepository(fresh_conn).get_all().iloc[0]["name"] == "NetRow"
    # 时间戳备份已写
    assert isolated_history and os.path.exists(isolated_history[0])


def test_adp_db_expired_falls_back_to_mock(fresh_conn, isolated_db, monkeypatch):
    """DB 快照过期 + CSV 不可用 + 禁网 → mock（且不回写 DB）。"""
    from fantasy_baseball.core import adp as adp_mod
    from fantasy_baseball.core.adp import ADPCache

    AdpRepository(fresh_conn).replace_all([{"name": "OldRow", "pos": "OF", "adp": 1.0}])
    fresh_conn.execute("UPDATE adp SET fetched_at = '2020-01-01 00:00:00'")
    fresh_conn.commit()

    cache = ADPCache()
    # _path_fresh 同时关掉根目录与 output/ 最近一份两层 CSV 回退
    monkeypatch.setattr(cache, "_path_fresh", lambda path: False)
    df = cache.fetch_adp(allow_network=False)
    assert len(df) == len(adp_mod._MOCK_ADP)
    # mock 不落库（H3 语义扩展）
    assert AdpRepository(fresh_conn).get_all().iloc[0]["name"] == "OldRow"


def test_adp_backfill_from_csv(fresh_conn, isolated_db, monkeypatch):
    """DB 为空 + CSV 有效 → CSV 数据自动回填入库；DB 已有数据时不覆盖。"""
    from fantasy_baseball.core.adp import ADPCache

    cache = ADPCache()
    if not os.path.exists(cache.adp_file):
        pytest.skip("无根目录 adp.csv（首次联网后生成），跳过回填测试")
    monkeypatch.setattr(cache, "_cache_valid", lambda: True)
    df = cache.fetch_adp(allow_network=False)
    n = AdpRepository(fresh_conn).count()
    assert n == len(df) and n > 0

    # DB 已有数据（哪怕过期）→ 回读 CSV 不覆盖 DB
    fresh_conn.execute("UPDATE adp SET fetched_at = datetime('now')")
    fresh_conn.commit()
    AdpRepository(fresh_conn).replace_all([{"name": "Kept", "pos": "OF", "adp": 1.0}])
    cache2 = ADPCache()
    monkeypatch.setattr(cache2, "_cache_valid", lambda: True)
    cache2.fetch_adp(allow_network=False)
    assert AdpRepository(fresh_conn).get_all().iloc[0]["name"] == "Kept"


# ============================================================
# 本地时间戳（回归：SQLite CURRENT_TIMESTAMP 曾写 UTC，差 8 小时）
# ============================================================
def test_timestamps_are_local(fresh_conn):
    """仓储写入的时间戳应与本地时间一致（±60s 容差），不再是 UTC。"""
    import time as _time
    from datetime import datetime as _dt

    from fantasy_baseball.db.repositories import _local_now

    def _parse(ts: str) -> float:
        return _time.mktime(_dt.strptime(ts, "%Y-%m-%d %H:%M:%S").timetuple())

    now = _time.time()

    AdpRepository(fresh_conn).replace_all([{"name": "A", "pos": "OF", "adp": 1.0}])
    ts = AdpRepository(fresh_conn).latest_fetch_time()
    assert abs(_parse(ts) - now) < 60, f"adp.fetched_at 偏离本地时间: {ts}"

    RankingsRepository(fresh_conn).replace_method("vorp", 2026, [{"rank": 1, "name": "A"}])
    ts = fresh_conn.execute(
        "SELECT MAX(generated_at) FROM rankings"
    ).fetchone()[0]
    assert abs(_parse(ts) - now) < 60, f"rankings.generated_at 偏离本地时间: {ts}"

    DraftLogRepository(fresh_conn).save_session("s", [{"round": 1, "name": "A"}])
    RecommendationRepository(fresh_conn).save_session("r", [{"name": "A"}])
    for table in ("draft_logs", "fa_recommendations"):
        ts = fresh_conn.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]
        assert abs(_parse(ts) - now) < 60, f"{table}.created_at 偏离本地时间: {ts}"


def test_adp_age_parses_local_timestamp():
    """TTL 年龄计算按本地时区解析（配合仓储写入的本地时间戳）。"""
    from datetime import datetime as _dt

    from fantasy_baseball.core.adp import ADPCache

    now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    age = ADPCache._age_seconds(now_str)
    assert 0 <= age < 60  # 刚写入 → 几乎为 0（若按 UTC 解析会差 8 小时）
    assert ADPCache._age_seconds("2020-01-01 00:00:00") > 86400 * 365
    assert ADPCache._age_seconds("garbage") == float("inf")


def test_adp_latest_csv_fallback(fresh_conn, isolated_db, tmpdir, monkeypatch):
    """审计回归：DB 过期 + 根目录 CSV 失效 + output/adp.csv 有效 → 读最近一份。

    旧实现漏了这层回退：TTL 过期 + 断网时磁盘上有真数据仍降级 25 条 mock。
    """
    from fantasy_baseball.core.adp import ADPCache
    from fantasy_baseball.core import adp as adp_mod

    AdpRepository(fresh_conn).replace_all([{"name": "OldRow", "pos": "OF", "adp": 1.0}])
    fresh_conn.execute("UPDATE adp SET fetched_at = '2020-01-01 00:00:00'")
    fresh_conn.commit()

    # 根目录 CSV：失效；「最近一份」：有效且内容不同
    monkeypatch.setattr(
        adp_mod, "output_path", lambda p: str(tmpdir.join("latest_adp.csv"))
    )
    pd.DataFrame({"name": ["LatestRow"], "pos": ["SS"], "adp": [7.0]}).to_csv(
        str(tmpdir.join("latest_adp.csv")), index=False
    )
    cache = ADPCache()
    calls = {"root": False}
    orig = cache._path_fresh
    def fake_fresh(path):
        if str(path) == cache.adp_file:
            return False  # 根目录旧文件失效
        return orig(path)
    monkeypatch.setattr(cache, "_path_fresh", fake_fresh)

    df = cache.fetch_adp(allow_network=False)
    assert df.iloc[0]["name"] == "LatestRow"
    assert cache.last_source == "csv_latest"


def test_history_path_no_collision_same_second(tmpdir, monkeypatch):
    """审计回归：同秒两次生成 history 备份不得互相覆盖。"""
    from fantasy_baseball import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "PROJECT_ROOT", str(tmpdir), raising=False)
    import importlib
    p1 = cfg_mod.history_path("rankings.csv")
    p2 = cfg_mod.history_path("rankings.csv")
    assert p1 != p2  # 毫秒时间戳 + 序号兜底


def test_write_csv_atomic_replaces(tmpdir):
    """审计回归：原子写替换旧文件且不留临时文件。"""
    import pandas as pd
    from fantasy_baseball.config import write_csv_atomic

    path = str(tmpdir.join("latest.csv"))
    write_csv_atomic(path, pd.DataFrame({"a": [1]}))
    write_csv_atomic(path, pd.DataFrame({"a": [2]}))
    df = pd.read_csv(path)
    assert df["a"].tolist() == [2]
    leftovers = [f for f in os.listdir(str(tmpdir)) if ".tmp." in f]
    assert leftovers == []


def test_session_id_milliseconds(fresh_conn, isolated_db):
    """审计回归：同秒两次 save_session 不再互相 DELETE。"""
    repo = DraftLogRepository(fresh_conn)
    # 模拟外部同 session_id（真正的防护在生成端毫秒），此处验证不同 id 并存
    repo.save_session("s_1", [{"round": 1, "name": "A"}])
    repo.save_session("s_2", [{"round": 1, "name": "B"}])
    assert repo.count() == 2
