"""数据导入：CSV → SQLite。

重写旧版 ``ingest_manual_csv_to_db.py``，用向量化操作和 executemany 替代逐行
``iterrows`` + ``execute``。支持多源加权融合与单源直拷。

CSV 列名（FanGraphs 风格 Name/Team/POS/K/9/BB/9）自动映射到 DB 列名
（name/team/pos/K_per_9/BB_per_9）。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from ..config import get_config, get_season, resolve_path
from ..db import PlayerRepository, db_session, init_db
from ..utils.logger import get_logger

logger = get_logger("ingestor")

# CSV 列名 → DB 列名映射（大小写不敏感）
COLUMN_MAP = {
    "name": "name", "team": "team", "pos": "pos", "source": "source",
    # 打者
    "r": "R", "hr": "HR", "rbi": "RBI", "sb": "SB",
    "avg": "AVG", "obp": "OBP", "slg": "SLG", "ops": "OPS", "pa": "PA",
    # 投手
    "w": "W", "l": "L", "sv": "SV", "hold": "HOLD",
    "era": "ERA", "whip": "WHIP",
    "k/9": "K_per_9", "k_per_9": "K_per_9",
    "bb/9": "BB_per_9", "bb_per_9": "BB_per_9",
    "ip": "IP",
}

HITTER_STATS = ["R", "HR", "RBI", "SB", "AVG", "OBP", "SLG", "OPS", "PA"]
PITCHER_STATS = ["W", "L", "SV", "HOLD", "ERA", "WHIP", "K_per_9", "BB_per_9", "IP"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """把 CSV 列名规范化为 DB 列名。"""
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_MAP:
            renamed[col] = COLUMN_MAP[key]
    return df.rename(columns=renamed)


class DataIngestor:
    """CSV 数据导入器。"""

    def __init__(self, conn=None):
        self._conn = conn
        self.config = get_config()

    # -------------------------------------------------------------- 公开 API
    def ingest_all(self) -> Dict[str, int]:
        """执行完整导入流程（位置 → 打者 → 投手 → 融合），返回各表行数。"""
        init_db() if self._conn is None else None
        logger.info("开始完整数据导入流程")
        self.ingest_positions()
        self.ingest_hitters()
        self.ingest_pitchers()
        self.merge_data()
        counts = self._run(lambda c: PlayerRepository(c).count())
        logger.info("数据导入完成: %s", counts)
        return counts

    def ingest_from_web(self, season: Optional[int] = None) -> dict:
        """从 FantasyPros 抓取预测数据并直接入库（无需手动 CSV）。

        同时自动填充位置映射（预测表的 Player 列含位置信息），
        解决旧版位置 CSV 也需手动准备的问题。

        Args:
            season: 赛季年份；None 则用配置/当前年（修复 H7）。

        Returns:
            各表行数字典。
        """
        from ..data_fetch.projections import fetch_projections

        season = season or get_season()
        logger.info("从网络抓取 %d 赛季预测数据", season)
        hitters_df = fetch_projections("hitters", season)
        pitchers_df = fetch_projections("pitchers", season)

        # 准备入库数据（保留 VORP + SGP 所需列），按 name 去重避免 UNIQUE 冲突
        hitter_cols = [c for c in ["name", "team", "pos", "R", "HR", "RBI", "SB",
                                   "AVG", "OBP", "SLG", "OPS", "PA",
                                   "AB", "H", "2B", "3B", "BB", "SO"]
                       if c in hitters_df.columns]
        pitcher_cols = [c for c in ["name", "team", "pos", "W", "L", "SV", "HOLD",
                                    "ERA", "WHIP", "K_per_9", "BB_per_9", "IP",
                                    "K", "ER", "H", "BB"]
                        if c in pitchers_df.columns]
        hitter_rows = hitters_df[hitter_cols].drop_duplicates(subset=["name"]).to_dict("records")
        pitcher_rows = pitchers_df[pitcher_cols].drop_duplicates(subset=["name"]).to_dict("records")

        # 投手的 H/BB 在 projections.py 里是投手被安打/被保送，DB 列名是 H_allow/BB_allow
        for r in pitcher_rows:
            if "H" in r:
                r["H_allow"] = r.pop("H")
            if "BB" in r:
                r["BB_allow"] = r.pop("BB")

        # 位置数据（从预测表的 name+pos 提取，按 name 去重避免 UNIQUE 冲突）
        position_map = {}
        for df in (hitters_df, pitchers_df):
            for _, r in df.iterrows():
                pos = r.get("pos")
                name = r.get("name")
                if pos and name and name not in position_map:
                    position_map[name] = {"name": name, "pos": pos, "team": r.get("team")}
        position_rows = list(position_map.values())

        def _do(conn):
            repo = PlayerRepository(conn)
            n_pos = repo.replace_positions(position_rows)
            # 打者/投手原始表（标 source=FP）
            hitter_src = [{**r, "source": "FP"} for r in hitter_rows]
            pitcher_src = [{**r, "source": "FP"} for r in pitcher_rows]
            n_h = repo.replace_hitters(hitter_src)
            n_p = repo.replace_pitchers(pitcher_src)
            # merged 表无 source 列，直接用原始 rows（FantasyPros 已是聚合值）
            n_mh = repo.replace_merged_hitters(hitter_rows)
            n_mp = repo.replace_merged_pitchers(pitcher_rows)
            return {
                "positions": n_pos,
                "hitters": n_h,
                "pitchers": n_p,
                "hitters_merged": n_mh,
                "pitchers_merged": n_mp,
            }

        counts = self._run(_do)
        logger.info("网络预测数据导入完成: %s", counts)
        return counts

    def ingest_positions(self) -> int:
        """导入球员位置映射。"""
        positions_file = resolve_path(self.config["data"]["positions_file"])
        if not os.path.exists(positions_file):
            logger.warning("位置映射文件不存在: %s", positions_file)
            return 0

        df = pd.read_csv(positions_file)
        if "Name" not in df.columns and "name" not in df.columns:
            logger.error("位置映射文件必须包含 Name 列")
            return 0
        if "POS" not in df.columns and "pos" not in df.columns:
            logger.error("位置映射文件必须包含 POS 列")
            return 0

        name_col = "Name" if "Name" in df.columns else "name"
        pos_col = "POS" if "POS" in df.columns else "pos"
        df = df[[name_col, pos_col]].dropna()
        df[name_col] = df[name_col].astype(str).str.strip()
        df[pos_col] = df[pos_col].astype(str).str.strip()

        rows = [{"name": r[name_col], "pos": r[pos_col], "team": None} for _, r in df.iterrows()]
        n = self._run(lambda c: PlayerRepository(c).replace_positions(rows))
        logger.info("导入 %d 条位置数据", n)
        return n

    def ingest_hitters(self) -> int:
        """导入打者预测数据（支持多源）。"""
        return self._ingest_players("hitters", HITTER_STATS)

    def ingest_pitchers(self) -> int:
        """导入投手预测数据（支持多源）。"""
        return self._ingest_players("pitchers", PITCHER_STATS)

    def merge_data(self) -> Dict[str, int]:
        """融合多源数据到 merged 表（或单源直拷）。"""
        if self.config["data"].get("use_multi_source"):
            n_h = self._merge_multi_source("hitters", HITTER_STATS)
            n_p = self._merge_multi_source("pitchers", PITCHER_STATS)
        else:
            n_h = self._copy_single_source("hitters", HITTER_STATS)
            n_p = self._copy_single_source("pitchers", PITCHER_STATS)
        return {"hitters_merged": n_h, "pitchers_merged": n_p}

    # -------------------------------------------------------------- 内部实现
    def _ingest_players(self, player_type: str, stats_cols: List[str]) -> int:
        """导入打者/投手原始数据（写入 hitters/pitchers 表）。"""
        use_multi = self.config["data"].get("use_multi_source")
        sources = self.config["projections"]["sources"] if use_multi else ["SINGLE"]

        all_rows: List[Dict] = []
        for source in sources:
            file_path = self._resolve_player_file(player_type, source)
            if not os.path.exists(file_path):
                logger.warning("%s 数据文件不存在: %s", player_type, file_path)
                continue
            logger.info("处理 %s 数据文件: %s (源: %s)", player_type, file_path, source)
            df = pd.read_csv(file_path)
            df = _normalize_columns(df)
            df["source"] = source
            all_rows.extend(self._df_to_rows(df, stats_cols))

        if not all_rows:
            logger.warning("没有可导入的 %s 数据", player_type)
            return 0

        def _do(conn):
            repo = PlayerRepository(conn)
            if player_type == "hitters":
                return repo.replace_hitters(all_rows)
            return repo.replace_pitchers(all_rows)

        n = self._run(_do)
        logger.info("导入 %d 条 %s 数据", n, player_type)
        return n

    def _resolve_player_file(self, player_type: str, source: str) -> str:
        """解析某数据源的文件路径。"""
        season = get_season(self.config)
        if not self.config["data"].get("use_multi_source"):
            # 修复 H7：文件名跟随生效赛季
            return resolve_path(f"data/{player_type}_{season}.csv")
        pattern = self.config["data"]["file_patterns"][player_type]
        # 支持 {source} / {season} 占位符（多余的 kwargs 会被 str.format 忽略）
        filename = pattern.format(source=source.lower(), season=season)
        return resolve_path(os.path.join("data", filename))

    @staticmethod
    def _df_to_rows(df: pd.DataFrame, stats_cols: List[str]) -> List[Dict]:
        """DataFrame 转为 dict 列表，只保留 name/team/pos/source + 统计列。"""
        keep = ["name", "team", "pos", "source"] + [c for c in stats_cols if c in df.columns]
        sub = df[[c for c in keep if c in df.columns]].copy()
        # 统计列转数值
        for c in stats_cols:
            if c in sub.columns:
                sub[c] = pd.to_numeric(sub[c], errors="coerce")
        return sub.to_dict("records")

    def _merge_multi_source(self, player_type: str, stats_cols: List[str]) -> int:
        """按权重加权融合多源数据。"""
        weights = self.config["projections"]["weights"]
        table = "hitters" if player_type == "hitters" else "pitchers"

        def _do(conn):
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            if df.empty:
                return 0

            # 把 source 映射到权重
            df["_weight"] = df["source"].map(lambda s: weights.get(str(s).upper(), 0))
            df = df[df["_weight"] > 0]
            if df.empty:
                return 0

            # 对每个统计列加权平均
            merged = df[["name"]].drop_duplicates().set_index("name")
            for c in ["team", "pos"]:
                merged[c] = df.groupby("name")[c].first()

            for col in stats_cols:
                if col not in df.columns:
                    continue
                vals = pd.to_numeric(df[col], errors="coerce")
                wsum = (vals * df["_weight"]).groupby(df["name"]).sum(min_count=1)
                wtot = df["_weight"].groupby(df["name"]).sum()
                merged[col] = wsum / wtot.replace(0, pd.NA)

            merged = merged.reset_index()
            rows = merged.to_dict("records")
            repo = PlayerRepository(conn)
            if player_type == "hitters":
                return repo.replace_merged_hitters(rows)
            return repo.replace_merged_pitchers(rows)

        n = self._run(_do)
        logger.info("融合 %d 条 %s 数据（多源）", n, player_type)
        return n

    def _copy_single_source(self, player_type: str, stats_cols: List[str]) -> int:
        """单源模式：把 hitters/pitchers 直接拷到 merged 表。"""
        src = "hitters" if player_type == "hitters" else "pitchers"
        dst = f"{src}_merged"

        def _do(conn):
            df = pd.read_sql_query(f"SELECT * FROM {src} WHERE source = 'SINGLE'", conn)
            if df.empty:
                # 兜底：若无 SINGLE 标记，拷贝全部
                df = pd.read_sql_query(f"SELECT * FROM {src}", conn)
            if df.empty:
                return 0
            keep = ["name", "team", "pos"] + [c for c in stats_cols if c in df.columns]
            rows = df[keep].to_dict("records")
            repo = PlayerRepository(conn)
            if player_type == "hitters":
                return repo.replace_merged_hitters(rows)
            return repo.replace_merged_pitchers(rows)

        n = self._run(_do)
        logger.info("拷贝 %d 条 %s 数据（单源）", n, player_type)
        return n

    # -------------------------------------------------------------- 工具
    def _run(self, func):
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
