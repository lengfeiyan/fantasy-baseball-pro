"""数据库连接管理。

用单一连接 + 上下文管理器统一管理，消除旧版 5 个类各自复制 connect_db /
disconnect_db 样板的问题。

用法::

    from fantasy_baseball.db import db_session

    with db_session() as conn:
        rows = conn.execute("SELECT * FROM hitters").fetchall()

首次调用会自动建表（幂等）。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from ..config import get_db_path
from ..utils.logger import get_logger
from .schema import create_all_tables

logger = get_logger("db")

# 单例连接 + 线程锁（sqlite3 连接默认 check_same_thread=True，跨线程使用需注意）
_connection: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取数据库连接。

    每次返回一个新的连接（SQLite 本地文件连接开销极小），确保数据在进程
    退出前持久化到磁盘。单例连接曾导致跨进程数据不可见的问题。

    Args:
        db_path: 可选的自定义数据库路径（主要用于测试）。

    Returns:
        sqlite3.Connection，row_factory 已设为 Row，支持按列名访问。
    """
    path = db_path if db_path is not None else get_db_path()
    # timeout=30：SQLite busy 等待从默认 5s 提到 30s，缓解 GUI 多线程
    # 并发 db_session 时偶发的 "database is locked"
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_all_tables(conn)
    conn.commit()  # 确保建表 DDL 提交
    return conn


@contextmanager
def db_session(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """数据库会话上下文管理器。

    正常退出时 commit 并关闭连接；异常时 rollback 并关闭。
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """显式初始化数据库（建表）。幂等，可安全多次调用。"""
    conn = get_connection(db_path)
    create_all_tables(conn)
    conn.commit()
    logger.info("数据库初始化完成")


def close_connection() -> None:
    """关闭单例连接（主要用于测试清理或程序退出）。"""
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
            _connection = None
