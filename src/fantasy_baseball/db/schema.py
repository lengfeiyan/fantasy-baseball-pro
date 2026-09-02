"""数据库表结构定义（集中管理）。

合并旧版 ``create_fa_tables.py`` 与 ``ingest_manual_csv_to_db.py._create_tables``
两处分散的建表逻辑，作为唯一的 schema 来源。所有 ``CREATE TABLE IF NOT EXISTS``，
幂等可重复执行。
"""

from __future__ import annotations

import sqlite3

from ..utils.logger import get_logger

logger = get_logger("db.schema")

# 打者原始预测（多源时每源一行，含 source 列）
HITTERS_SQL = """
CREATE TABLE IF NOT EXISTS hitters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    team TEXT,
    pos TEXT,
    eligible_pos TEXT,
    source TEXT,
    R REAL, HR REAL, RBI REAL, SB REAL,
    AVG REAL, OBP REAL, SLG REAL, OPS REAL, PA REAL,
    AB REAL, H REAL, "2B" REAL, "3B" REAL, BB REAL, SO REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 投手原始预测
PITCHERS_SQL = """
CREATE TABLE IF NOT EXISTS pitchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    team TEXT,
    pos TEXT,
    source TEXT,
    W REAL, L REAL, SV REAL, HOLD REAL,
    ERA REAL, WHIP REAL, K_per_9 REAL, BB_per_9 REAL, IP REAL,
    K REAL, ER REAL, H_allow REAL, BB_allow REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 球员位置映射
PLAYER_POSITIONS_SQL = """
CREATE TABLE IF NOT EXISTS player_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    pos TEXT,
    team TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 融合后的打者数据（多源加权结果，无 source 列）
HITTERS_MERGED_SQL = """
CREATE TABLE IF NOT EXISTS hitters_merged (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    team TEXT,
    pos TEXT,
    eligible_pos TEXT,
    R REAL, HR REAL, RBI REAL, SB REAL,
    AVG REAL, OBP REAL, SLG REAL, OPS REAL, PA REAL,
    AB REAL, H REAL, "2B" REAL, "3B" REAL, BB REAL, SO REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 融合后的投手数据
PITCHERS_MERGED_SQL = """
CREATE TABLE IF NOT EXISTS pitchers_merged (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    team TEXT,
    pos TEXT,
    W REAL, L REAL, SV REAL, HOLD REAL,
    ERA REAL, WHIP REAL, K_per_9 REAL, BB_per_9 REAL, IP REAL,
    K REAL, ER REAL, H_allow REAL, BB_allow REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# FA 自由球员池（player_id 为独立标识，不强引用 hitters，因 FA 球员通常不在已选池中）
FA_POOL_SQL = """
CREATE TABLE IF NOT EXISTS fa_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    name TEXT,
    team TEXT,
    pos TEXT,
    status TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 球员赛季统计（EAV 长表，stat_type/value）
PLAYER_SEASON_STATS_SQL = """
CREATE TABLE IF NOT EXISTS player_season_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    name TEXT,
    team TEXT,
    pos TEXT,
    stat_type TEXT,
    value REAL,
    game_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 用户阵容（player_id 为独立标识，不强引用 hitters——修复审计高危项：
# 旧版保留的 FOREIGN KEY 让"去外键迁移"判据永远为真，每次打开连接都
# DROP+重建该表；恢复时外键违反的行被静默丢弃，造成永久数据丢失）
USER_ROSTER_SQL = """
CREATE TABLE IF NOT EXISTS user_roster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    name TEXT,
    team TEXT,
    pos TEXT,
    status TEXT,
    acquisition_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 伤病报告（player_id 为独立标识，不强引用 hitters）
INJURY_REPORTS_SQL = """
CREATE TABLE IF NOT EXISTS injury_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    name TEXT,
    injury_type TEXT,
    severity TEXT,
    start_date DATE,
    expected_return DATE,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# ===== 数据统一入库（DB 为唯一数据源，CSV 转为时间戳历史备份）=====

# ADP 快照（每次抓取整体替换；TTL 看 fetched_at）
ADP_SQL = """
CREATE TABLE IF NOT EXISTS adp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    team TEXT,
    pos TEXT,
    adp REAL,
    source TEXT DEFAULT 'FantasyPros',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 排名快照（按 method 整体替换，永远代表最新一次生成）
RANKINGS_SQL = """
CREATE TABLE IF NOT EXISTS rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    season INTEGER,
    rank INTEGER,
    name TEXT,
    team TEXT,
    pos TEXT,
    player_type TEXT,
    vorp REAL,
    vorp_upside REAL,
    vorp_floor REAL,
    sgp_total REAL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 选秀日志（会话式追加：一次模拟一个 session_id，支持多顺位对比）
DRAFT_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS draft_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    method TEXT,
    strategy TEXT,
    user_pick INTEGER,
    round INTEGER,
    pick INTEGER,
    team INTEGER,
    name TEXT,
    team_name TEXT,
    pos TEXT,
    vorp REAL,
    sgp_total REAL,
    adp REAL,
    is_user_pick INTEGER,
    is_value_pick INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# FA 推荐记录（会话式追加）
FA_RECOMMENDATIONS_SQL = """
CREATE TABLE IF NOT EXISTS fa_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    method TEXT,
    risk_preference TEXT,
    player_id INTEGER,
    name TEXT,
    team TEXT,
    pos TEXT,
    final_score REAL,
    overall_value REAL,
    base_score REAL,
    statcast_score REAL,
    need_factor REAL,
    risk_adjustment REAL,
    is_mock INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 新秀雷达快照（F7，会话式追加：一次抓取一个 fetched_at，
# 保留 rank/composite 历史序列，供 rank 变动与 post-hype 检测使用）
PROSPECT_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS prospect_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER,
    rank INTEGER,
    name TEXT,
    mlb_id INTEGER,
    position TEXT,
    age INTEGER,
    team TEXT,
    levels TEXT,
    top_level TEXT,
    proximity TEXT,
    tier TEXT,
    composite REAL,
    value_gap REAL,
    adp REAL,
    payload TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_hitters_name ON hitters(name)",
    "CREATE INDEX IF NOT EXISTS idx_pitchers_name ON pitchers(name)",
    "CREATE INDEX IF NOT EXISTS idx_hitters_merged_name ON hitters_merged(name)",
    "CREATE INDEX IF NOT EXISTS idx_pitchers_merged_name ON pitchers_merged(name)",
    "CREATE INDEX IF NOT EXISTS idx_fa_pool_pos ON fa_pool(pos)",
    "CREATE INDEX IF NOT EXISTS idx_fa_pool_name ON fa_pool(name)",
    "CREATE INDEX IF NOT EXISTS idx_player_season_stats_player ON player_season_stats(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_roster_pos ON user_roster(pos)",
    "CREATE INDEX IF NOT EXISTS idx_user_roster_name ON user_roster(name)",
    "CREATE INDEX IF NOT EXISTS idx_injury_reports_player ON injury_reports(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_injury_reports_name ON injury_reports(name)",
    "CREATE INDEX IF NOT EXISTS idx_adp_name ON adp(name)",
    "CREATE INDEX IF NOT EXISTS idx_rankings_query ON rankings(method, season, rank)",
    "CREATE INDEX IF NOT EXISTS idx_draft_logs_session ON draft_logs(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_fa_recs_session ON fa_recommendations(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_prospect_snap_query ON prospect_snapshots(season, fetched_at)",
    "CREATE INDEX IF NOT EXISTS idx_prospect_snap_name ON prospect_snapshots(name)",
]

ALL_TABLE_SQL = [
    HITTERS_SQL,
    PITCHERS_SQL,
    PLAYER_POSITIONS_SQL,
    HITTERS_MERGED_SQL,
    PITCHERS_MERGED_SQL,
    FA_POOL_SQL,
    PLAYER_SEASON_STATS_SQL,
    USER_ROSTER_SQL,
    INJURY_REPORTS_SQL,
    ADP_SQL,
    RANKINGS_SQL,
    DRAFT_LOGS_SQL,
    FA_RECOMMENDATIONS_SQL,
    PROSPECT_SNAPSHOTS_SQL,
]


def create_all_tables(conn: sqlite3.Connection) -> None:
    """在给定连接上创建所有表与索引（幂等）。

    对于旧版带 FOREIGN KEY 的表（fa_pool/injury_reports/user_roster/
    player_season_stats），检测到旧 schema 会 DROP 后用新 schema 重建——
    这些表的数据均为抓取/导入的可重建数据，迁移安全。
    """
    cursor = conn.cursor()
    _migrate_legacy_fk_tables(conn)
    for sql in ALL_TABLE_SQL:
        cursor.execute(sql)
    for sql in INDEXES_SQL:
        cursor.execute(sql)
    # 恢复迁移时备份的数据
    _restore_migrated_data(conn)
    # 给旧表补 SGP 需要的新列（ALTER TABLE ADD COLUMN，幂等）
    _add_sgp_columns(conn)
    # 不在此 commit，由调用方（connection 层 / db_session）负责


def _add_sgp_columns(conn: sqlite3.Connection) -> None:
    """给 hitters/pitchers 及其 merged 表补 SGP 所需列。

    ALTER TABLE ADD COLUMN 幂等：已存在的列会抛 OperationalError，捕获跳过。
    """
    # 表 → 新增列列表
    migrations = {
        "hitters": ["AB", "H", "2B", "3B", "BB", "SO"],
        "hitters_merged": ["AB", "H", "2B", "3B", "BB", "SO"],
        "pitchers": ["K", "ER", "H_allow", "BB_allow"],
        "pitchers_merged": ["K", "ER", "H_allow", "BB_allow"],
    }
    for table, cols in migrations.items():
        # 先看表是否存在 + 已有哪些列
        try:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error:
            continue  # 表不存在，跳过（CREATE 时会建新的）
        if not existing:
            continue
        for col in cols:
            if col not in existing:
                try:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" REAL')
                except sqlite3.OperationalError:
                    pass  # 列已存在（并发情况）

    # eligible_pos（多位置资格，"2B,SS" 逗号分隔）——projections 计算该列，
    # scoring 的多位置 VORP 依赖它（修复审计项：此前从未入库，该逻辑是死代码）
    for table in ("hitters", "hitters_merged"):
        try:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error:
            continue
        if existing and "eligible_pos" not in existing:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN eligible_pos TEXT")
            except sqlite3.OperationalError:
                pass


def _migrate_legacy_fk_tables(conn: sqlite3.Connection) -> None:
    """检测并重建旧版带外键的表（改为无外键的新 schema）。

    旧版 fa_pool/injury_reports/user_roster/player_season_stats 有
    ``FOREIGN KEY (player_id) REFERENCES hitters(id)``，会阻止插入 FA 球员。
    新版去掉了这些外键。此函数幂等：已是新 schema 则跳过。
    迁移时保留原有数据（备份 → DROP → 重建 → 恢复）。
    """
    tables_to_check = ("fa_pool", "player_season_stats", "user_roster", "injury_reports")
    for table in tables_to_check:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not row:
            continue  # 表不存在，CREATE 时会建新的
        create_sql = row[0] if isinstance(row[0], str) else row[0].decode("utf-8")
        if "FOREIGN KEY" not in create_sql.upper():
            continue  # 已是新 schema
        # 旧 schema → 保留数据迁移
        # 1. 读取现有数据
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            col_names = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
        except sqlite3.Error:
            rows, col_names = [], []
        # 2. DROP 旧表
        conn.execute(f"DROP TABLE {table}")
        # 3. CREATE 由后续 create_all_tables 完成
        # 4. 数据恢复推迟到表重建后（在 create_all_tables 之后调 _restore_migrated_data）
        conn.execute("CREATE TABLE IF NOT EXISTS _migration_backup (table_name TEXT, data TEXT)")
        import json
        conn.execute(
            "INSERT INTO _migration_backup VALUES (?, ?)",
            (table, json.dumps([dict(r) for r in rows])),
        )


def _restore_migrated_data(conn: sqlite3.Connection) -> None:
    """恢复迁移备份的数据到新表（在 create_all_tables 之后调用）。"""
    import json
    try:
        rows = conn.execute("SELECT table_name, data FROM _migration_backup").fetchall()
    except sqlite3.Error:
        return
    if not rows:
        return
    for row in rows:
        table = row[0]
        data = json.loads(row[1])
        if not data:
            continue
        cols = list(data[0].keys())
        # 只插入新表里存在的列
        try:
            table_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            existing_cols = {c[1] for c in table_info}
        except sqlite3.Error:
            continue
        valid_cols = [c for c in cols if c in existing_cols]
        if not valid_cols:
            continue
        placeholders = ",".join("?" * len(valid_cols))
        col_list = ",".join(valid_cols)
        failed = 0
        for record in data:
            values = [record.get(c) for c in valid_cols]
            try:
                conn.execute(
                    f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
                    values,
                )
            except sqlite3.Error as e:
                # 修复审计项：不再静默吞错——失败的行会永久丢失，必须留痕
                failed += 1
                logger.warning(
                    "迁移恢复 %s 失败一行（数据: %s）: %s", table, record, e
                )
        if failed:
            logger.warning("表 %s 迁移恢复完成：%d/%d 行失败被跳过", table, failed, len(data))
    conn.execute("DROP TABLE IF EXISTS _migration_backup")


def list_tables(conn: sqlite3.Connection) -> list:
    """返回数据库中所有用户表名（调试用）。"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]
