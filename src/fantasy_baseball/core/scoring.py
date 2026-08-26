"""统一的 VORP 与风险评分模型。

消除旧版三套 VORP 实现（fantasy_scoring_model_v2 / scoring/vorp_calculator /
fa_analyzer.fa_analyzer）的重复，以旧版 ``fantasy_scoring_model_v2`` 的 quantile
替代水平法为基础，结果与之保持一致。

算法：
- 打者：score = Σ(stat × weight)；按位置的 25 分位数为替代水平；vorp = score − replacement
- 投手：score = Σ(stat × weight)；全体的 25 分位数为替代水平；vorp = score − replacement
- 风险：z_score 法用 std ± adjustment；historical_variance 用比例缩放
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from ..config import get_config, get_season, history_path, output_path, write_csv_atomic
from ..db import PlayerRepository, db_session
from ..utils.logger import get_logger

logger = get_logger("scoring")

# 默认输出列顺序
RANKING_COLUMNS = [
    "rank", "name", "team", "pos", "player_type",
    "vorp", "vorp_upside", "vorp_floor", "score",
]


class ScoringModel:
    """统一的球员评分与排名生成。"""

    def __init__(self, conn=None):
        """Args:
            conn: 可选的数据库连接。不传则每次计算时通过 db_session() 获取。
        """
        self._conn = conn
        cfg = get_config()
        self.scoring_rules = cfg["league"]["scoring"]
        self.risk_method = cfg["risk_model"]["method"]
        self.risk_adjustment = cfg["risk_model"]["adjustment_factor"]
        # 动态替代水平配置
        self.league_size = cfg["league"]["size"]
        self.roster_slots = cfg["league"]["roster_slots"]
        self.total_slots = sum(self.roster_slots.values())
        # stream 席位：这些位置上的球员本质上就是替代水平球员（日替/stream FA）
        # 默认 5（SP 轮换 + setup RP + UTIL 等），可在 config.yaml 调整
        self.stream_slots = cfg.get("scoring", {}).get("stream_slots", 5)

    def _replacement_quantile(self, total_players: int, pos_slots: int = 1) -> float:
        """计算替代水平对应的分位数。

        基于"该位置被选的固定球员数"算替代水平位置：
        - 每队该位置的 slot 数 × 联盟队伍数 = 该位置总被选人数
        - 其中一部分是 stream 席位（替代水平球员），从总被选数中减去
        - 替代水平 = 固定被选球员中排名最后那个

        Args:
            total_players: 该位置/分组的球员总数。
            pos_slots: 该位置每队的 roster slot 数（如 OF=4, SS=1）。

        Returns:
            分位数（0-1），用于 quantile()。
        """
        if total_players <= 0:
            return 0.25  # 兜底

        # 该位置被选的总人数（每队 pos_slots 个 × 队伍数）
        drafted = self.league_size * pos_slots

        # stream 席位按各位置 slot 占比分摊
        if self.total_slots > 0:
            stream_this_pos = self.stream_slots * pos_slots / self.total_slots
        else:
            stream_this_pos = 0

        # 固定球员数 = 被选数 - stream 分摊
        fixed = max(1, drafted - stream_this_pos)

        # 分位数方向（修复审计高危项）：替代水平 = 固定被选球员中的最后一名
        # （分数降序第 fixed 名），对应升序分位点 1 - fixed/total。
        # 旧实现 q = fixed/total 取的是升序第 fixed 名（池内第 N 差的球员），
        # 方向颠倒：中游球员 VORP 符号翻转，跨位置比较系统性失真。
        q = 1.0 - fixed / total_players
        return max(0.10, min(0.90, q))

    # ------------------------------------------------------------------ VORP
    def calculate_vorp(self) -> pd.DataFrame:
        """计算所有球员的 VORP 与风险评分，返回带 rank 的 DataFrame。"""
        logger.info("开始计算 VORP...")

        def _do(conn):
            repo = PlayerRepository(conn)
            hitters = repo.get_merged_hitters()
            pitchers = repo.get_merged_pitchers()
            if hitters.empty and pitchers.empty:
                raise ValueError("数据库中没有融合后的球员数据，请先运行数据导入")
            return hitters, pitchers

        hitters_df, pitchers_df = self._run(_do)

        if not hitters_df.empty:
            hitters_df = self._calculate_hitter_vorp(hitters_df.copy())
        if not pitchers_df.empty:
            pitchers_df = self._calculate_pitcher_vorp(pitchers_df.copy())

        all_df = pd.concat(
            [df for df in (hitters_df, pitchers_df) if not df.empty],
            ignore_index=True,
        )
        all_df = self._calculate_risk_scores(all_df)
        all_df = all_df.sort_values("vorp", ascending=False).reset_index(drop=True)
        all_df["rank"] = range(1, len(all_df) + 1)
        logger.info("VORP 计算完成，共 %d 名球员", len(all_df))
        return all_df

    def _calculate_hitter_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算打者 VORP（按位置动态替代水平 + 多位置灵活性 bonus）。"""
        df["score"] = self._compute_score(df, self.scoring_rules["hitters"])

        replacement_levels = {}
        for pos in df["pos"].dropna().unique():
            if pos == "UTIL":
                # UTIL 无真实替代基准（专职 DH 池极小，直接分位数会被 clip
                # 到个位数）：用全体打者池按打者总槽位的动态分位数
                total_slots = sum(
                    v for k, v in self.roster_slots.items() if k not in ("SP", "RP")
                )
                q_all = self._replacement_quantile(len(df), max(1, total_slots))
                replacement_levels["UTIL"] = df["score"].quantile(q_all)
                continue
            pos_scores = df.loc[df["pos"] == pos, "score"]
            if len(pos_scores) > 0:
                pos_slots = self.roster_slots.get(pos, 1)
                q = self._replacement_quantile(len(pos_scores), pos_slots)
                replacement_levels[pos] = pos_scores.quantile(q)

        def _calc_vorp(row):
            score = row["score"]
            primary_pos = row.get("pos", "")
            # 多位置资格：取所有合格位置中替代水平最低的（即 VORP 最高的位置）。
            # 审计回归修复：UTIL 不参与多位置比较——UTIL 不是真实替代基准
            # （UTIL 池只有极少数专职 DH，替代水平被 clip 到 8 分左右），
            # 192/855 打者的 eligible_pos 带 UTIL，一旦参与比较全部落到
            # UTIL 拿到虚高 VORP（均值 +34，最高 +298）。
            eligible = row.get("eligible_pos", "")
            if eligible and isinstance(eligible, str) and "," in eligible:
                best_vorp = None
                for p in eligible.split(","):
                    p = p.strip()
                    if p == "UTIL":
                        continue
                    repl = replacement_levels.get(p, replacement_levels.get(primary_pos, 0))
                    v = score - repl
                    if best_vorp is None or v > best_vorp:
                        best_vorp = v
                vorp = best_vorp if best_vorp is not None else score - replacement_levels.get(primary_pos, 0)
            else:
                vorp = score - replacement_levels.get(primary_pos, 0)
            return vorp

        df["vorp"] = df.apply(_calc_vorp, axis=1)
        df["player_type"] = "hitter"
        return df

    def _calculate_pitcher_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算投手 VORP（SP/RP 分别按动态替代水平）。"""
        df["score"] = self._compute_score(df, self.scoring_rules["pitchers"])

        # 按 SP/RP 分组算替代水平
        replacements = {}
        for pos in ("SP", "RP"):
            pos_scores = df.loc[df["pos"] == pos, "score"]
            if len(pos_scores) > 0:
                pos_slots = self.roster_slots.get(pos, 1)
                q = self._replacement_quantile(len(pos_scores), pos_slots)
                replacements[pos] = pos_scores.quantile(q)
        # 兜底：无位置信息的用全体替代水平
        total_pitcher_slots = self.roster_slots.get("SP", 4) + self.roster_slots.get("RP", 3)
        overall_q = self._replacement_quantile(len(df), total_pitcher_slots)
        overall = df["score"].quantile(overall_q)

        df["vorp"] = df.apply(
            lambda row: row["score"] - replacements.get(row.get("pos"), overall),
            axis=1,
        )
        df["player_type"] = "pitcher"
        return df

    @staticmethod
    def _compute_score(df: pd.DataFrame, weights: dict) -> pd.Series:
        """根据评分规则加权求和，忽略不存在的列。"""
        score = pd.Series(0.0, index=df.index)
        for stat, weight in weights.items():
            if stat in df.columns:
                score = score + pd.to_numeric(df[stat], errors="coerce").fillna(0) * weight
        return score

    # ------------------------------------------------------------------ 风险
    def _calculate_risk_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 vorp_upside / vorp_floor。"""
        if self.risk_method == "z_score":
            for ptype in ("hitter", "pitcher"):
                mask = df["player_type"] == ptype
                if mask.sum() > 1:
                    std = df.loc[mask, "vorp"].std()
                    if pd.isna(std):
                        std = 0
                    df.loc[mask, "vorp_upside"] = df.loc[mask, "vorp"] + std * self.risk_adjustment
                    df.loc[mask, "vorp_floor"] = df.loc[mask, "vorp"] - std * self.risk_adjustment
        elif self.risk_method == "historical_variance":
            # 修复审计项：负 VORP 直接乘 (1±adj) 会让 upside < floor（方向反转）。
            # 改为在 vorp 两侧对称展开 ±adj×|vorp|，正负值方向均正确
            # （正值时与旧公式 vorp*(1±adj) 等价）。
            spread = self.risk_adjustment * df["vorp"].abs()
            df["vorp_upside"] = df["vorp"] + spread
            df["vorp_floor"] = df["vorp"] - spread
        else:
            spread = 0.1 * df["vorp"].abs()
            df["vorp_upside"] = df["vorp"] + spread
            df["vorp_floor"] = df["vorp"] - spread

        # 单行组（std 无定义）回落到 ±10% 展开法，避免 NaN 写入排名 CSV
        if "vorp_upside" not in df.columns:
            df["vorp_upside"] = float("nan")
        if "vorp_floor" not in df.columns:
            df["vorp_floor"] = float("nan")
        need = df["vorp_upside"].isna() | df["vorp_floor"].isna()
        if need.any():
            fallback = 0.1 * df.loc[need, "vorp"].abs()
            df.loc[need, "vorp_upside"] = df.loc[need, "vorp"] + fallback
            df.loc[need, "vorp_floor"] = df.loc[need, "vorp"] - fallback

        # floor 不为负
        if "vorp_floor" in df.columns:
            df["vorp_floor"] = df["vorp_floor"].clip(lower=0)
        else:
            df["vorp_upside"] = df["vorp"]
            df["vorp_floor"] = df["vorp"].clip(lower=0)

        return df

    # -------------------------------------------------------------- 输出排名
    def generate_rankings(self, output_file: Optional[str] = None) -> str:
        """生成排名并持久化（DB 当前状态 + 时间戳历史备份 + 最近一份同名 CSV）。

        Returns:
            「最近一份」CSV 的绝对路径（时间戳备份在同目录 history/ 子目录）。
        """
        cfg = get_config()
        season = get_season(cfg)
        if output_file is None:
            # 修复 H7：文件名跟随生效赛季，不再硬编码
            output_file = f"fantasy_draft_rankings_vorp_{season}.csv"

        rankings = self.calculate_vorp()
        for col in RANKING_COLUMNS:
            if col not in rankings.columns:
                rankings[col] = None
        rankings = rankings[RANKING_COLUMNS]

        # 1. DB（当前状态，按 method 整体替换）
        try:
            from ..db import RankingsRepository, db_session

            with db_session() as conn:
                RankingsRepository(conn).replace_method(
                    "vorp", season, rankings.to_dict("records")
                )
            logger.info("VORP 排名已写入数据库（%d 名球员）", len(rankings))
        except Exception as e:
            logger.warning("VORP 排名写入数据库失败: %s", e)

        # 2. CSV：最近一份（原子替换）+ 时间戳历史备份
        path = output_path(output_file)
        try:
            write_csv_atomic(path, rankings)
        except OSError as e:
            # 最近一份写失败不应中断——历史备份仍要尝试（审计低危项：
            # 此前此处未捕获，异常直接抛出导致备份代码不执行）
            logger.warning("写入排名最近一份 CSV 失败: %s", e)
        try:
            backup = history_path(output_file)
            rankings.to_csv(backup, index=False)
        except OSError as e:
            logger.warning("写入排名历史备份失败: %s", e)

        logger.info("排名文件已保存: %s（%d 名球员）", path, len(rankings))
        if len(rankings) > 0:
            top = rankings.iloc[0]
            logger.info("排名第一: %s (VORP: %.2f)", top["name"], top["vorp"])
        return path

    # -------------------------------------------------------------- 内部工具
    def _run(self, func):
        """在自有连接或 db_session 中执行 func(conn)。"""
        if self._conn is not None:
            return func(self._conn)
        with db_session() as conn:
            return func(conn)
