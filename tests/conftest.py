"""pytest 全局 fixture。

关键设计：每个测试使用独立的临时数据库和临时配置，避免污染全局单例
（修复旧测试修改全局 config 导致用例间相互影响的问题）。
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

# 让 src/ 在 import 路径上（无需 pip install -e .）
import sys
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


@pytest.fixture
def tmp_db_path(tmpdir):
    """临时数据库文件路径。"""
    return str(tmpdir.join("test.db"))


@pytest.fixture
def fresh_conn(tmp_db_path):
    """提供一个全新的、独立的数据库连接（不污染单例）。

    测试中所有需要 DB 的代码都应通过传入 conn 参数使用此连接。
    """
    import sqlite3
    from fantasy_baseball.db.schema import create_all_tables

    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_all_tables(conn)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def reset_config_cache():
    """每个测试后重置配置单例缓存，避免跨用例污染。"""
    yield
    import fantasy_baseball.config as cfgmod
    cfgmod._cache = None


@pytest.fixture
def sample_hitters():
    """样例打者数据。"""
    return [
        {"name": "Player A", "team": "TM", "pos": "OF", "R": 100, "HR": 30,
         "RBI": 90, "SB": 20, "AVG": 0.300, "OBP": 0.380, "SLG": 0.550,
         "OPS": 0.930, "PA": 650},
        {"name": "Player B", "team": "TM", "pos": "1B", "R": 80, "HR": 35,
         "RBI": 100, "SB": 2, "AVG": 0.280, "OBP": 0.350, "SLG": 0.500,
         "OPS": 0.850, "PA": 620},
        {"name": "Player C", "team": "TM", "pos": "SS", "R": 70, "HR": 15,
         "RBI": 60, "SB": 25, "AVG": 0.260, "OBP": 0.330, "SLG": 0.420,
         "OPS": 0.750, "PA": 600},
    ]


@pytest.fixture
def sample_pitchers():
    """样例投手数据。"""
    return [
        {"name": "Pitcher A", "team": "TM", "pos": "SP", "W": 18, "L": 6,
         "SV": 0, "HOLD": 0, "ERA": 2.60, "WHIP": 1.05,
         "K_per_9": 11.5, "BB_per_9": 2.2, "IP": 200},
        {"name": "Pitcher B", "team": "TM", "pos": "RP", "W": 4, "L": 3,
         "SV": 30, "HOLD": 5, "ERA": 3.20, "WHIP": 1.15,
         "K_per_9": 10.0, "BB_per_9": 3.0, "IP": 60},
    ]
