"""数据库访问层。

提供统一的连接管理与仓储模式。业务代码通过 ``db_session()`` 获取连接，
通过仓储类（``PlayerRepository`` 等）访问数据，不再各自维护连接。
"""

from .connection import db_session, get_connection, init_db
from .repositories import (
    FaRepository,
    InjuryRepository,
    PlayerRepository,
    RosterRepository,
)
from .schema import create_all_tables

__all__ = [
    "db_session",
    "get_connection",
    "init_db",
    "create_all_tables",
    "PlayerRepository",
    "FaRepository",
    "InjuryRepository",
    "RosterRepository",
]
