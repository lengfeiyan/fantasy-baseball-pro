"""数据访问仓储层。

业务代码通过仓储类访问数据，不再直接持有连接或写裸 SQL。每个仓储接收一个
``sqlite3.Connection``（通常由 ``db_session()`` 提供），所有方法都在该连接上操作，
事务由 ``db_session()`` 统一管理。
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


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


class PlayerRepository(_BaseRepository):
    """打者 / 投手 / 位置 / 融合数据的访问。"""

    # 打者原始数据
    def replace_hitters(self, hitters: Sequence[Dict[str, Any]]) -> int:
        """批量写入打者原始数据（先清空再插入，用于多源场景）。"""
        self.conn.execute("DELETE FROM hitters")
        if not hitters:
            return 0
        cols = list(hitters[0].keys())
        sql = self._build_insert_sql("hitters", cols)
        self.conn.executemany(sql, [tuple(h[c] for c in cols) for h in hitters])
        return len(hitters)

    def replace_pitchers(self, pitchers: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM pitchers")
        if not pitchers:
            return 0
        cols = list(pitchers[0].keys())
        sql = self._build_insert_sql("pitchers", cols)
        self.conn.executemany(sql, [tuple(p[c] for c in cols) for p in pitchers])
        return len(pitchers)

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
        if not rows:
            return 0
        cols = list(rows[0].keys())
        sql = self._build_insert_sql("hitters_merged", cols)
        self.conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        return len(rows)

    def replace_merged_pitchers(self, rows: Sequence[Dict[str, Any]]) -> int:
        self.conn.execute("DELETE FROM pitchers_merged")
        if not rows:
            return 0
        cols = list(rows[0].keys())
        sql = self._build_insert_sql("pitchers_merged", cols)
        self.conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        return len(rows)

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
