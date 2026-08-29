"""模拟战绩榜（Projected Standings，F1）。

SGP 体系的杀手级应用：把一支阵容各统计类别的预测总量，按 SGP 分母
折算成"相对联盟平均的名次积分"，再模拟 12 支同类球队的分布，输出
**每个类别的期望名次**与总 SGP——"我这个阵容 HR 争第 2、SB 只能第 9"。

方法（标准 SGP standings 投影）：
1. 联盟平均队基准：计数类用典型总量（R 950 / HR 245 ...），比率类用
   SGP 模型的假想团队基准（.267 AVG / 3.59 ERA / 1.23 WHIP）。
2. 你的阵容各类别加总；与平均队的差 ÷ 分母 = 该类别 SGP 增益。
3. 其他 league_size−1 支球队以平均队为中心、按类别经验波动（CV）
   正态生成 2000 次模拟 → 你的各类别**期望名次**。
4. 总 SGP = 各类别增益之和；总榜名次 = 用同样的其他队模拟按总增益
   排名得到。

局限（诚实声明）：其他球队用统计模型而非真实对手阵容（P4a 接入后可
换真实数据）；比率类名次对阵容构成敏感，仅供横向参考。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import get_config
from ..utils.logger import get_logger
from .sgp import SGPModel

logger = get_logger("standings")

# 联盟平均队的计数类典型总量（12 队经验值，与 SGP 假想团队基准同源）
_LEAGUE_AVG_COUNTING = {
    "R": 950.0, "HR": 245.0, "RBI": 930.0, "SB": 125.0,
    "W": 78.0, "SV": 62.0, "K": 1280.0,
}

# 其他球队的类别波动（变异系数，12 队经验值）：SB/SV 波动最大
_CATEGORY_CV = {
    "R": 0.055, "HR": 0.09, "RBI": 0.055, "SB": 0.16,
    "W": 0.12, "SV": 0.22, "K": 0.07,
}

_SIM_ROUNDS = 2000


class ProjectedStandings:
    """基于 SGP 分母的模拟战绩榜。"""

    def __init__(self, sgp_model: Optional[SGPModel] = None):
        self.sgp = sgp_model or SGPModel()
        cfg = get_config()
        self.league_size = cfg["league"]["size"]
        self.roster_slots = cfg["league"]["roster_slots"]
        self._rng = np.random.default_rng(42)

    # -------------------------------------------------------------- 公开 API
    def project(
        self,
        roster: pd.DataFrame,
        stats_source: Optional[pd.DataFrame] = None,
        hitters_source: Optional[pd.DataFrame] = None,
        pitchers_source: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """投影一支阵容的模拟战绩。

        Args:
            roster: 阵容 DataFrame（需含 pos/name 列与统计列；来自
                user_roster 或选秀日志 is_user_pick 子集）。缺统计列时自动
                按 name 从 merged 表补齐。
            stats_source: 兼容别名，等价于同时传 hitters_source 与
                pitchers_source（阵容全是打者/混合且想共用一份来源时用）。
            hitters_source / pitchers_source: 测试或外部数据源直传
                merged 帧（避免内部 db_session 连到真实库）。

        Returns:
            {
              "categories": [ {category, team_value, league_avg, sgp, exp_rank}, ... ],
              "total_sgp": 阵容相对平均队的总 SGP 增益,
              "exp_total_rank": 总榜期望名次,
              "league_size": 联盟规模,
            }
            exp_rank 为 None 表示该类别数据不足、无法模拟名次（sgp 仍有效）。
        """
        if roster is None or roster.empty:
            raise ValueError("阵容为空，无法生成模拟战绩（先导入阵容或跑选秀模拟）")

        roster = self._attach_stats(
            roster,
            hitters_source=(
                hitters_source if hitters_source is not None else stats_source
            ),
            pitchers_source=(
                pitchers_source if pitchers_source is not None else stats_source
            ),
        )

        d = dict(self.sgp.hitter_denoms)
        d.update(self.sgp.pitcher_denoms)
        others_n = self.league_size - 1

        results: List[Dict[str, Any]] = []
        total_sgp = 0.0
        total_sgp_sims = np.zeros(_SIM_ROUNDS)

        # ---- 计数类：总量直接比较
        for cat, avg in _LEAGUE_AVG_COUNTING.items():
            team_value = self._col_sum(roster, cat)
            denom = d.get(cat)
            if team_value is None or not denom:
                continue
            sgp_gain = (team_value - avg) / denom
            total_sgp += sgp_gain

            others = self._rng.normal(
                avg, max(avg * _CATEGORY_CV.get(cat, 0.08), 1e-9),
                size=(_SIM_ROUNDS, others_n),
            )
            # 名次 = 1 + 比你高的球队数（均值）
            better = (others > team_value).sum(axis=1)
            exp_rank = float(1 + better.mean())
            # 总榜模拟：其他队该类别的随机增益
            total_sgp_sims += (others - avg).mean(axis=1) / denom

            results.append({
                "category": cat,
                "team_value": round(float(team_value), 1),
                "league_avg": round(avg, 1),
                "sgp": round(float(sgp_gain), 2),
                "exp_rank": round(exp_rank, 1),
            })

        # ---- 比率类：对率值，用"阵容贡献拉动的 SGP"估计名次
        ratio_rows = self._ratio_categories(roster, d, others_n)
        for row in ratio_rows:
            total_sgp += row["sgp"]
            results.append(row)

        results.sort(key=lambda r: r["category"])

        # ---- 总榜期望名次：每次模拟中其他队总增益高于我的队数 +1，取均值
        my_total = total_sgp
        if others_n > 0:
            exp_total_rank = float(1 + np.mean(
                (total_sgp_sims[:, None] > my_total).sum(axis=1)
            ))
        else:
            exp_total_rank = 1.0

        return {
            "categories": results,
            "total_sgp": round(float(total_sgp), 2),
            "exp_total_rank": round(exp_total_rank, 1),
            "league_size": self.league_size,
        }

    # -------------------------------------------------------------- 内部
    @staticmethod
    def _attach_stats(
        roster: pd.DataFrame,
        hitters_source: Optional[pd.DataFrame] = None,
        pitchers_source: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """阵容缺统计列时（user_roster 只有身份列），从 merged 表按姓名补齐。

        打者列来自 hitters_merged、投手列来自 pitchers_merged；补充的
        投手 H/BB 映射为 H_allow/BB_allow。已有列不覆盖。
        hitters_source / pitchers_source：外部直传 merged 帧（测试隔离用），
        缺省时经 db_session 读真实库。
        """
        needed_h = ("R", "HR", "RBI", "SB", "AB", "H")
        needed_p = ("W", "SV", "K", "IP", "ER", "H_allow", "BB_allow")
        have = set(roster.columns)
        need_h = [c for c in needed_h if c not in have]
        need_p = [c for c in needed_p if c not in have]
        if not need_h and not need_p:
            return roster

        roster = roster.copy()

        def _apply(src: Optional[pd.DataFrame], cols: List[str], renames: Dict[str, str]) -> int:
            """把 src 按姓名映射进 roster，返回补到值的列数。"""
            filled = 0
            if src is None or src.empty:
                return 0
            stats = src.set_index("name")
            for c in cols:
                target = renames.get(c, c)
                if target in roster.columns or c not in stats.columns:
                    continue
                roster[target] = roster["name"].map(stats[c])
                filled += 1
            return filled

        def _load(kind: str) -> Optional[pd.DataFrame]:
            explicit = hitters_source if kind == "hitters" else pitchers_source
            if explicit is not None:
                return explicit
            try:
                from ..db import PlayerRepository, db_session

                with db_session() as conn:
                    return (
                        PlayerRepository(conn).get_merged_hitters()
                        if kind == "hitters"
                        else PlayerRepository(conn).get_merged_pitchers()
                    )
            except Exception as e:
                logger.warning("读取 %s merged 表失败: %s", kind, e)
                return None

        if need_h:
            n = _apply(_load("hitters"), need_h, {})
            need_h = [c for c in need_h if c not in roster.columns]
        if need_p:
            # 投手 H/BB 在 merged 表即 H_allow/BB_allow
            n2 = _apply(_load("pitchers"), need_p, {})
            need_p = [c for c in need_p if c not in roster.columns]

        stat_cols = [c for c in needed_h + needed_p if c in roster.columns]
        if stat_cols:
            n_without_stats = int(roster[stat_cols].isna().all(axis=1).sum())
            if n_without_stats:
                logger.warning(
                    "%d 名阵容球员在预测库中无记录，其统计按 0 计（名次会偏悲观）",
                    n_without_stats,
                )
        return roster

    @staticmethod
    def _col_sum(roster: pd.DataFrame, col: str) -> Optional[float]:
        if col not in roster.columns:
            return None
        s = pd.to_numeric(roster[col], errors="coerce").fillna(0)
        total = float(s.sum())
        return total if total > 0 else None

    def _ratio_categories(
        self, roster: pd.DataFrame, d: Dict[str, float], others_n: int
    ) -> List[Dict[str, Any]]:
        """AVG/ERA/WHIP：阵容贡献量对联盟平均队的拉动 → SGP（无名次模拟，
        率值不是可加总量，名次意义有限，exp_rank 置 None）。"""
        out: List[Dict[str, Any]] = []
        ip = pd.to_numeric(roster.get("IP"), errors="coerce") if "IP" in roster.columns else None

        # AVG：阵容 AB/H 加到假想团队
        ab = pd.to_numeric(roster.get("AB"), errors="coerce") if "AB" in roster.columns else None
        h = pd.to_numeric(roster.get("H"), errors="coerce") if "H" in roster.columns else None
        if ab is not None and h is not None:
            t_ab, t_h = float(ab.fillna(0).sum()), float(h.fillna(0).sum())
            if t_ab > 0:
                sgp = ((t_h + 1768.0) / (t_ab + 6617.0) - 0.267) / d.get("AVG", 0.0024)
                out.append({"category": "AVG", "team_value": round(t_h / t_ab, 3),
                            "league_avg": 0.267, "sgp": round(float(sgp), 2), "exp_rank": None})

        # ERA
        er = pd.to_numeric(roster.get("ER"), errors="coerce") if "ER" in roster.columns else None
        if ip is not None and er is not None:
            t_ip, t_er = float(ip.fillna(0).sum()), float(er.fillna(0).sum())
            if t_ip > 0:
                era = t_er * 9 / t_ip
                sgp = ((t_er + 475.0) * 9 / (t_ip + 1192.0) - 3.59) / d.get("ERA", -0.076)
                out.append({"category": "ERA", "team_value": round(era, 2),
                            "league_avg": 3.59, "sgp": round(float(sgp), 2), "exp_rank": None})

        # WHIP
        h_allow = pd.to_numeric(roster.get("H_allow"), errors="coerce") if "H_allow" in roster.columns else None
        bb_allow = pd.to_numeric(roster.get("BB_allow"), errors="coerce") if "BB_allow" in roster.columns else None
        if ip is not None and h_allow is not None and bb_allow is not None:
            t_ip = float(ip.fillna(0).sum())
            allow = float(h_allow.fillna(0).sum() + bb_allow.fillna(0).sum())
            if t_ip > 0:
                whip = allow / t_ip
                sgp = ((allow + 1466.0) / (t_ip + 1192.0) - 1.23) / d.get("WHIP", -0.015)
                out.append({"category": "WHIP", "team_value": round(whip, 3),
                            "league_avg": 1.23, "sgp": round(float(sgp), 2), "exp_rank": None})
        return out
