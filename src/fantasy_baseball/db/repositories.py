"""数据访问仓储层。

业务代码通过仓储类访问数据，不再直接持有连接或写裸 SQL。每个仓储接收一个
``sqlite3.Connection``（通常由 ``db_session()`` 提供），所有方法都在该连接上操作，
事务由 ``db_session()`` 统一管理。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _local_now() -> str:
    """本地时间的字符串形式（YYYY-MM-DD HH:MM:SS）。

    修复审计反馈：SQLite 的 CURRENT_TIMESTAMP 默认写 UTC，与用户本地时间
    差时区（中国 +8h），表里时间戳"不对"。所有业务写入显式传本地时间，
    表定义里的 DEFAULT 仅作兜底。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class _BaseRepository:
    """仓储基类，持有共享的连接。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def _build_insert_sql(table: str, cols: list) -> str:
        """构造 INSERT 语句，列名加双引号（兼容 2B/3B 等数字开头列名）。"""
        quoted = ",".join(f'"{c}"' for c in cols)
        placeholders = ",".join("?" * len(cols))
        return f'INSERT INTO {table} ({quoted}) VALUES ({placeholders})'

    def _insert_rows(self, table: str, rows: Sequence[Dict[str, Any]]) -> int:
        """按全部行列集的并集批量插入，缺失的键填 NULL。

        修复审计发现的问题：按第一行列集建 INSERT 时，后续行多出的列
        触发 KeyError、少掉的列导致该列整批丢失。
        """
        if not rows:
            return 0
        cols: List[str] = []
        for r in rows:
            for k in r.keys():
                if k not in cols:
                    cols.append(k)
        sql = self._build_insert_sql(table, cols)
        self.conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        return len(rows)


class PlayerRepository(_BaseRepository):
    """打者 / 投手 / 位置 / 融合数据的访问。"""

    # 打者原始数据
    def replace_hitters(self, hitters: Sequence[Dict[str, Any]]) -> int:
        """批量写入打者原始数据（先清空再插入，用于多源场景）。

        行与行列集不一致时按并集对齐、缺的填 NULL（修复审计发现的
        「按第一行列集建 INSERT → KeyError/整列静默丢弃」问题）。
        """
        self.conn.execute("DELETE FROM hitters")
        return self._insert_rows("hitters", hitters)

    def replace_pitchers(self, pitchers: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM pitchers")
        return self._insert_rows("pitchers", pitchers)

    def replace_positions(self, positions: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM player_positions")
        if not positions:
            return 0
        self.conn.executemany(
            "INSERT INTO player_positions(name, pos, team) VALUES(?,?,?)",
            [(p["name"], p.get("pos"), p.get("team")) for p in positions],
        )
        return len(positions)

    # 融合数据
    def replace_merged_hitters(self, rows: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM hitters_merged")
        return self._insert_rows("hitters_merged", rows)

    def replace_merged_pitchers(self, rows: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM pitchers_merged")
        return self._insert_rows("pitchers_merged", rows)

    # 读取（返回 DataFrame，供评分模块使用）
    def get_merged_hitters(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM hitters_merged", self.conn)

    def get_merged_pitchers(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM pitchers_merged", self.conn)

    def get_hitters(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM hitters", self.conn)

    def get_pitchers(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM pitchers", self.conn)

    def get_positions(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM player_positions", self.conn)

    def count(self) -> Dict[str, int]:
        """返回各表行数（诊断用）。"""
        counts = {}
        for t in ("hitters", "pitchers", "hitters_merged", "pitchers_merged", "player_positions"):
            counts[t] = self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return counts


class FaRepository(_BaseRepository):
    """FA 池访问。"""

    def replace_pool(self, rows: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM fa_pool")
        if not rows:
            return 0
        self.conn.executemany(
            "INSERT INTO fa_pool(player_id, name, team, pos, status) VALUES(?,?,?,?,?)",
            [
                (r.get("player_id"), r.get("name"), r.get("team"), r.get("pos"), r.get("status"))
                for r in rows
            ],
        )
        return len(rows)

    def add_to_pool(self, row: Dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO fa_pool(player_id, name, team, pos, status) VALUES(?,?,?,?,?)",
            (
                row.get("player_id"),
                row.get("name"),
                row.get("team"),
                row.get("pos"),
                row.get("status"),
            ),
        )
        return cur.lastrowid

    def get_pool(self, position: Optional[str] = None) -> pd.DataFrame:
        if position and position != "All":
            return pd.read_sql_query(
                "SELECT * FROM fa_pool WHERE pos = ?", self.conn, params=(position,)
            )
        return pd.read_sql_query("SELECT * FROM fa_pool", self.conn)

    def find_in_pool(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM fa_pool WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM fa_pool").fetchone()[0]

    def remove_from_pool(self, name: str) -> bool:
        cur = self.conn.execute("DELETE FROM fa_pool WHERE name = ?", (name,))
        return cur.rowcount > 0


class RosterRepository(_BaseRepository):
    """用户阵容访问。"""

    def add_player(self, row: Dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO user_roster(player_id, name, team, pos, status) VALUES(?,?,?,?,?)",
            (
                row.get("player_id"),
                row.get("name"),
                row.get("team"),
                row.get("pos"),
                row.get("status", "active"),
            ),
        )
        return cur.lastrowid

    def replace_all(self, rows: Sequence[Dict[str, Any]]) -> int:
        """清空并批量写入阵容。"""
        self.clear()
        if not rows:
            return 0
        self.conn.executemany(
            "INSERT INTO user_roster(player_id, name, team, pos, status) VALUES(?,?,?,?,?)",
            [
                (r.get("player_id"), r.get("name"), r.get("team"), r.get("pos"), r.get("status", "active"))
                for r in rows
            ],
        )
        return len(rows)

    def remove_player(self, name: str) -> bool:
        cur = self.conn.execute("DELETE FROM user_roster WHERE name = ?", (name,))
        return cur.rowcount > 0

    def get_roster(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM user_roster", self.conn)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM user_roster").fetchone()[0]

    def clear(self) -> None:
        self.conn.execute("DELETE FROM user_roster")


class InjuryRepository(_BaseRepository):
    """伤病报告访问。"""

    def replace_all(self, rows: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM injury_reports")
        if not rows:
            return 0
        self.conn.executemany(
            """INSERT INTO injury_reports
               (player_id, name, injury_type, severity, start_date, expected_return, status)
               VALUES(?,?,?,?,?,?,?)""",
            [
                (
                    r.get("player_id"),
                    r.get("name"),
                    r.get("injury_type"),
                    r.get("severity"),
                    r.get("start_date"),
                    r.get("expected_return"),
                    r.get("status"),
                )
                for r in rows
            ],
        )
        return len(rows)

    def add(self, row: Dict[str, Any]) -> int:
        cur = self.conn.execute(
            """INSERT INTO injury_reports
               (player_id, name, injury_type, severity, start_date, expected_return, status)
               VALUES(?,?,?,?,?,?,?)""",
            (
                row.get("player_id"),
                row.get("name"),
                row.get("injury_type"),
                row.get("severity"),
                row.get("start_date"),
                row.get("expected_return"),
                row.get("status"),
            ),
        )
        return cur.lastrowid

    def get_all(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM injury_reports", self.conn)

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM injury_reports WHERE name = ? ORDER BY created_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM injury_reports").fetchone()[0]


class AdpRepository(_BaseRepository):
    """ADP 快照访问（每次抓取整体替换，永远代表最新一批）。"""

    def replace_all(
        self, rows: Sequence[Dict[str, Any]], fetched_at: Optional[str] = None
    ) -> int:
        """整体替换 ADP 快照（rows 含 name/team/pos/adp，source 可选）。

        Args:
            fetched_at: 显式指定数据时间（"YYYY-MM-DD HH:MM:SS"）。
                CSV 回填时传文件 mtime——旧数据不得借回填获得全新 TTL
                租期（审计低危项：租期曾最长翻倍）。默认当前本地时间。
        """
        self.conn.execute("DELETE FROM adp")
        if not rows:
            return 0
        ts = fetched_at or _local_now()
        self.conn.executemany(
            """INSERT INTO adp(name, team, pos, adp, source, fetched_at)
               VALUES(?,?,?,?,COALESCE(?, 'FantasyPros'),?)""",
            [
                (r.get("name"), r.get("team"), r.get("pos"), r.get("adp"), r.get("source"), ts)
                for r in rows
            ],
        )
        return len(rows)

    def get_all(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM adp", self.conn)

    def latest_fetch_time(self) -> Optional[str]:
        """最新一批的 fetched_at（TTL 判断用）。空表返回 None。"""
        row = self.conn.execute(
            "SELECT MAX(fetched_at) FROM adp"
        ).fetchone()
        return row[0] if row and row[0] else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM adp").fetchone()[0]


class RankingsRepository(_BaseRepository):
    """排名快照访问（按 method 整体替换）。"""

    def replace_method(self, method: str, season: int, rows: Sequence[Dict[str, Any]]) -> int:
        """替换指定 method 的排名快照（另一 method 不受影响）。"""
        self.conn.execute("DELETE FROM rankings WHERE method = ?", (method,))
        if not rows:
            return 0
        ts = _local_now()
        self.conn.executemany(
            """INSERT INTO rankings(method, season, rank, name, team, pos, player_type,
                                   vorp, vorp_upside, vorp_floor, sgp_total, generated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (method, season, r.get("rank"), r.get("name"), r.get("team"),
                 r.get("pos"), r.get("player_type"), r.get("vorp"),
                 r.get("vorp_upside"), r.get("vorp_floor"), r.get("sgp_total"), ts)
                for r in rows
            ],
        )
        return len(rows)

    def get_latest(self, method: str) -> pd.DataFrame:
        """取指定 method 最新一批的排名（按 generated_at 分组的最新组）。"""
        return pd.read_sql_query(
            """SELECT * FROM rankings
               WHERE method = ?
                 AND generated_at = (SELECT MAX(generated_at) FROM rankings WHERE method = ?)
               ORDER BY rank""",
            self.conn, params=(method, method),
        )

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM rankings").fetchone()[0]


class DraftLogRepository(_BaseRepository):
    """选秀日志访问（会话式：一次模拟一个 session_id）。"""

    def save_session(
        self, session_id: str, rows: Sequence[Dict[str, Any]],
        method: str = "vorp", strategy: str = "balanced", user_pick: int = 1,
    ) -> int:
        """写入一次模拟的完整日志（同 session_id 先清后写，保证幂等）。"""
        self.conn.execute("DELETE FROM draft_logs WHERE session_id = ?", (session_id,))
        if not rows:
            return 0
        ts = _local_now()
        self.conn.executemany(
            """INSERT INTO draft_logs(session_id, method, strategy, user_pick,
                                      round, pick, team, name, team_name, pos,
                                      vorp, sgp_total, adp, is_user_pick, is_value_pick,
                                      created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (session_id, method, strategy, user_pick,
                 r.get("round"), r.get("pick"), r.get("team"), r.get("name"),
                 r.get("team_name"), r.get("pos"), r.get("vorp"), r.get("sgp_total"),
                 r.get("adp"),
                 1 if r.get("is_user_pick") else 0,
                 1 if r.get("is_value_pick") else 0,
                 ts)
                for r in rows
            ],
        )
        return len(rows)

    def get_session(self, session_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM draft_logs WHERE session_id = ? ORDER BY pick",
            self.conn, params=(session_id,),
        )

    def latest_session_id(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT session_id FROM draft_logs ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def latest_session(self) -> pd.DataFrame:
        """最近一次模拟的日志（GUI「从最近模拟导入阵容」用）。"""
        sid = self.latest_session_id()
        if sid is None:
            return pd.DataFrame()
        return self.get_session(sid)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM draft_logs").fetchone()[0]


class RecommendationRepository(_BaseRepository):
    """FA 推荐记录访问（会话式）。"""

    def save_session(
        self, session_id: str, rows: Sequence[Dict[str, Any]],
        method: str = "vorp", risk_preference: str = "balanced",
    ) -> int:
        self.conn.execute(
            "DELETE FROM fa_recommendations WHERE session_id = ?", (session_id,)
        )
        if not rows:
            return 0
        ts = _local_now()
        self.conn.executemany(
            """INSERT INTO fa_recommendations(session_id, method, risk_preference,
                                             player_id, name, team, pos,
                                             final_score, overall_value, base_score,
                                             statcast_score, need_factor, risk_adjustment, is_mock,
                                             created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (session_id, method, risk_preference,
                 r.get("player_id"), r.get("name"), r.get("team"), r.get("pos"),
                 r.get("final_score"), r.get("overall_value"), r.get("base_score"),
                 r.get("statcast_score"), r.get("need_factor"), r.get("risk_adjustment"),
                 1 if r.get("is_mock") else 0,
                 ts)
                for r in rows
            ],
        )
        return len(rows)

    def get_session(self, session_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM fa_recommendations WHERE session_id = ? ORDER BY final_score DESC",
            self.conn, params=(session_id,),
        )

    def latest_session_id(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT session_id FROM fa_recommendations ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM fa_recommendations").fetchone()[0]


class ProspectRepository(_BaseRepository):
    """新秀雷达快照访问（F7，会话式追加：一次抓取一个 fetched_at）。

    与 ADP 的"整体替换"语义不同——这里刻意保留历史批次，
    同一球员的 rank/composite 序列是 post-hype 与 rank 变动检测的原始数据。
    """

    _COLUMNS = ("season", "rank", "name", "mlb_id", "position", "age", "team",
                "levels", "top_level", "proximity", "tier", "composite",
                "value_gap", "adp", "payload")

    def save_snapshot(self, rows: Sequence[Dict[str, Any]], season: int,
                      fetched_at: Optional[str] = None) -> int:
        """追加一批快照（rows 为雷达输出行，payload 存完整行 JSON）。"""
        if not rows:
            return 0
        import json
        ts = fetched_at or _local_now()
        self.conn.executemany(
            """INSERT INTO prospect_snapshots(
                   season, rank, name, mlb_id, position, age, team,
                   levels, top_level, proximity, tier, composite,
                   value_gap, adp, payload, fetched_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    season, r.get("rank"), r.get("name"), r.get("mlb_id"),
                    r.get("position"), r.get("age"), r.get("team"),
                    r.get("levels"), r.get("top_level"), r.get("proximity"),
                    r.get("tier"), r.get("composite"), r.get("value_gap"),
                    r.get("adp"),
                    json.dumps(r, ensure_ascii=False) if r.get("payload") is None else str(r["payload"]),
                    ts,
                )
                for r in rows
            ],
        )
        return len(rows)

    def get_latest_snapshot(self, season: int) -> pd.DataFrame:
        """该赛季最新一批快照（按 fetched_at 取最大值对应的整批）。"""
        row = self.conn.execute(
            "SELECT MAX(fetched_at) FROM prospect_snapshots WHERE season = ?",
            (season,),
        ).fetchone()
        if not row or not row[0]:
            return pd.DataFrame()
        return pd.read_sql_query(
            "SELECT * FROM prospect_snapshots WHERE season = ? AND fetched_at = ?"
            " ORDER BY rank",
            self.conn, params=(season, row[0]),
        )

    def rank_history(self, name: str, season: int) -> pd.DataFrame:
        """单个球员的 rank/composite 历史序列（post-hype 检测用）。"""
        return pd.read_sql_query(
            "SELECT fetched_at, rank, composite, tier, proximity"
            " FROM prospect_snapshots WHERE season = ? AND name = ?"
            " ORDER BY fetched_at",
            self.conn, params=(season, name),
        )
