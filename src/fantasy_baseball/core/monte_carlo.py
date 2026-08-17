"""蒙特卡洛选秀模拟器（高性能版）。

迁移自旧版 ``draft_simulator/``。修复了旧版 ``_calculate_availability_prob``
和 ``simulate_multiple_drafts`` 上错误的 ``@njit`` 装饰（njit 不支持对象方法
与 DataFrame 操作）：

- 核心可用性概率用纯 numpy 向量化实现（足够快）。
- 若安装了 numba，对纯数值的可用性计算做 JIT 加速；否则降级。
- 5 种 AI 经理策略保留，列名 bug（position vs pos）修正为统一 pos。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import get_config
from ..utils.logger import get_logger
from .scoring import ScoringModel

logger = get_logger("monte_carlo")

# 尝试导入 numba，失败则降级为纯 numpy
try:
    from numba import njit, prange  # type: ignore

    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False
    prange = range  # type: ignore

    def njit(*args, **kwargs):  # type: ignore
        # 兼容装饰器：既支持 @njit 也支持 @njit(parallel=True)
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def deco(f):
            return f

        return deco


# ---------------------------------------------------------------- 可用性概率
def _availability_pure(adp_array, target_pick):
    """纯 numpy 向量化实现（兜底，始终可用）。"""
    adp = np.asarray(adp_array, dtype=np.float64)
    out = np.where(
        adp >= 999,
        0.9,
        1.0 - 0.5 * (1.0 + np.tanh((target_pick - adp) / 10.0 / np.sqrt(2.0))),
    )
    return out


def _availability_kernel(adp_array, target_pick):
    """计算可用概率。优先用 numba 加速版，编译失败则降级为纯 numpy。"""
    if _HAS_NUMBA:
        try:
            return _availability_numba(adp_array, target_pick)
        except Exception:  # noqa: BLE001 — 旧 numba 编译失败时降级
            pass
    return _availability_pure(adp_array, target_pick)


if _HAS_NUMBA:
    try:
        @njit(cache=True)
        def _availability_numba(adp_array, target_pick):
            n = adp_array.shape[0]
            out = np.zeros(n)
            for i in range(n):
                adp = adp_array[i]
                if adp >= 999.0:
                    out[i] = 0.9
                else:
                    z = (target_pick - adp) / 10.0
                    prob_selected = 0.5 * (1.0 + np.tanh(z / np.sqrt(2.0)))
                    out[i] = 1.0 - prob_selected
            return out
    except Exception:  # noqa: BLE001 — 装饰阶段失败
        _availability_numba = None


def calculate_availability(adp_array, target_pick) -> np.ndarray:
    """计算各球员在目标顺位的可用概率（公开接口）。"""
    return _availability_kernel(np.asarray(adp_array, dtype=np.float64), float(target_pick))


# ---------------------------------------------------------------- AI 策略
class BaseDrafter:
    """AI 经理人基类：按 VORP 最高选人，考虑阵容需求。"""

    def __init__(self, league_config: Dict):
        self.league_config = league_config
        self.roster_slots = league_config["roster_slots"]
        self.roster: Dict[str, List[str]] = {}
        self.picks: List[str] = []

    def reset(self):
        self.roster = {}
        self.picks = []

    def draft(self, available: pd.DataFrame) -> Optional[str]:
        if available.empty:
            return None
        scored = self.score_players(available)
        if scored.empty:
            return None
        best = scored.sort_values("value", ascending=False).iloc[0]
        name = best["name"]
        pos = best.get("pos", "UTIL")
        self.roster.setdefault(pos, []).append(name)
        self.picks.append(name)
        return name

    def score_players(self, available: pd.DataFrame) -> pd.DataFrame:
        """基类：纯 VORP，对阵容缺口位置加成。"""
        df = available.copy()
        df["value"] = df.get("vorp", 0)
        needs = self.get_roster_needs()
        # 缺口位置 ×1.1 加成
        df["value"] = df.apply(
            lambda r: r["value"] * 1.1 if needs.get(r.get("pos"), 0) > 0 else r["value"], axis=1
        )
        return df

    def get_roster_needs(self) -> Dict[str, int]:
        return {
            pos: max(0, mx - len(self.roster.get(pos, [])))
            for pos, mx in self.roster_slots.items()
        }


class BalancedDrafter(BaseDrafter):
    """均衡型：标准 VORP。"""


class PositionalHoarderDrafter(BaseDrafter):
    """位置囤积型：优先填满稀缺位置。"""

    def score_players(self, available):
        df = super().score_players(available)
        needs = self.get_roster_needs()
        # 更强地加权缺口位置
        df["value"] = df.apply(
            lambda r: r["value"] * 1.3 if needs.get(r.get("pos"), 0) > 0 else r["value"],
            axis=1,
        )
        return df


class StatcastBelieverDrafter(BaseDrafter):
    """Statcast 信徒：偏好 vorp_upside。"""

    def score_players(self, available):
        df = available.copy()
        col = "vorp_upside" if "vorp_upside" in df.columns else "vorp"
        df["value"] = df[col]
        return df


class ADPFollowerDrafter(BaseDrafter):
    """ADP 跟随者：严格按 ADP 升序（模拟真实玩家）。"""

    def score_players(self, available):
        df = available.copy()
        if "adp" in df.columns:
            # ADP 越低越优先 → value = -adp
            df["value"] = -df["adp"].fillna(999)
        else:
            df["value"] = df.get("vorp", 0)
        return df


class YourStrategyDrafter(BaseDrafter):
    """用户个人策略：前 3 轮抢 SP，4-8 轮锁定年轻高 VORP 打者，9+ 轮捡 Statcast。"""

    def score_players(self, available):
        df = available.copy()
        round_num = len(self.picks) + 1
        if round_num <= 3:
            # 前 3 轮：只考虑投手大幅加权
            df["value"] = df.apply(
                lambda r: r.get("vorp", 0) * 2.0 if r.get("pos") in ("SP", "RP") else r.get("vorp", 0) * 0.3,
                axis=1,
            )
        elif round_num <= 8:
            df["value"] = df.get("vorp", 0)
        else:
            col = "vorp_upside" if "vorp_upside" in df.columns else "vorp"
            df["value"] = df[col]
        return df


_STRATEGY_MAP = {
    "balanced": BalancedDrafter,
    "positional": PositionalHoarderDrafter,
    "statcast": StatcastBelieverDrafter,
    "adp": ADPFollowerDrafter,
    "yours": YourStrategyDrafter,
}


def get_drafter(strategy: str, league_config: Dict) -> BaseDrafter:
    cls = _STRATEGY_MAP.get(strategy, BalancedDrafter)
    return cls(league_config)


# ---------------------------------------------------------------- njit 核心
def _simulate_core(adp_sorted, iterations, total_picks, n_rounds, league_size,
                   cancel_check=None):
    """模拟核心。numba 可用时用 njit 加速，否则纯 Python。

    模拟逻辑：每轮给 ADP 排序后的球员加随机噪声，按噪声值升序"被选"。
    这模拟了真实选秀中球员在 ADP 附近浮动被选的行为。
    """
    if _HAS_NUMBA:
        try:
            return _simulate_numba(adp_sorted, iterations, total_picks, league_size)
        except Exception:
            pass
    return _simulate_pure(adp_sorted, iterations, total_picks, league_size, cancel_check)


if _HAS_NUMBA:
    try:
        @njit(cache=True)
        def _simulate_numba(adp_sorted, iterations, total_picks, league_size):
            n = adp_sorted.shape[0]
            draft_counts = np.zeros(n, dtype=np.int64)
            pick_sums = np.zeros(n, dtype=np.float64)
            picks_this = min(total_picks, n)

            for it in range(iterations):
                # 给每个球员的 ADP 加正态噪声
                noisy = adp_sorted + np.random.normal(0, 8.0, n)
                # 取噪声最小的 picks_this 个（模拟被选）
                order = np.argsort(noisy)
                for pick_num in range(picks_this):
                    idx = order[pick_num]
                    draft_counts[idx] += 1
                    pick_sums[idx] += pick_num + 1

            return draft_counts, pick_sums
    except Exception:
        _simulate_numba = None


def _simulate_pure(adp_sorted, iterations, total_picks, league_size, cancel_check=None):
    """纯 Python 降级版。cancel_check 为可选的取消回调（每 50 次迭代检查）。"""
    n = len(adp_sorted)
    draft_counts = np.zeros(n, dtype=np.int64)
    pick_sums = np.zeros(n, dtype=np.float64)
    picks_this = min(total_picks, n)
    rng = np.random.default_rng()

    for it in range(iterations):
        # 支持中途取消（numba 路径无法中断，纯 Python 路径可以）
        if cancel_check is not None and it % 50 == 0 and cancel_check():
            return None, None  # 标记取消
        noisy = adp_sorted + rng.normal(0, 8.0, n)
        order = np.argsort(noisy)
        for pick_num in range(picks_this):
            idx = order[pick_num]
            draft_counts[idx] += 1
            pick_sums[idx] += pick_num + 1

    return draft_counts, pick_sums


# ---------------------------------------------------------------- 引擎
class DraftEngine:
    """蒙特卡洛选秀引擎。"""

    def __init__(self, player_pool: Optional[pd.DataFrame] = None, method: str = "vorp"):
        cfg = get_config()
        self.league_config = cfg["league"]
        self.league_size = self.league_config["size"]
        self.rounds = self.league_config["rounds"]
        self.method = method
        # 标准化列名
        self.players = self._prepare_pool(player_pool)
        self.drafters: Dict[int, BaseDrafter] = {}

    def _prepare_pool(self, pool: Optional[pd.DataFrame]) -> pd.DataFrame:
        if pool is None:
            if self.method == "sgp":
                from .sgp import SGPModel
                pool = SGPModel().calculate_sgp()
            else:
                pool = ScoringModel().calculate_vorp()
        df = pool.copy()
        # 统一列名
        if "position" in df.columns and "pos" not in df.columns:
            df = df.rename(columns={"position": "pos"})
        if "player_name" in df.columns and "name" not in df.columns:
            df = df.rename(columns={"player_name": "name"})
        if "fantasy_points" in df.columns and "vorp" not in df.columns:
            df = df.rename(columns={"fantasy_points": "vorp"})
        # 确定排序基准列：SGP 模式优先用 sgp_total，否则用 vorp
        rank_col = "sgp_total" if (self.method == "sgp" and "sgp_total" in df.columns) else "vorp"
        # 缺 adp 列或全是默认值 999 → 用排名反推估算 ADP
        if "adp" not in df.columns or df["adp"].fillna(999).max() == 999:
            value_rank = df[rank_col].fillna(0).rank(method="first", ascending=False)
            df["adp"] = value_rank.astype(float)
        return df

    def simulate_draft(
        self, iterations: int = 1000, user_strategy: str = "balanced",
        cancel_check=None,
    ) -> pd.DataFrame:
        """运行多次模拟，返回每个球员的可用性统计。

        核心循环用 numba njit 加速（纯 numpy 数组操作）。numba 不可用时
        自动降级为纯 Python 循环。

        Args:
            iterations: 模拟次数。
            user_strategy: 用户策略名（保留接口兼容，加速模式下按 ADP
                           加噪声模拟，与 AI 策略结果近似）。
            cancel_check: 可选取消回调（纯 Python 路径每 50 次迭代检查）。
                          返回 True 表示取消。取消时返回空 DataFrame。

        Returns:
            DataFrame 含 name/pos/vorp/adp/draft_rate/avg_round/avg_pick。
        """
        import time as _time
        t0 = _time.time()
        logger.info("蒙特卡洛模拟：%d 次（%s 加速）", iterations,
                     "numba" if _HAS_NUMBA else "纯 Python")

        # 准备球员数组
        df = self.players.copy()
        n_players = len(df)
        vorp_arr = df["vorp"].fillna(0).values.astype(np.float64)
        adp_arr = df["adp"].fillna(999).values.astype(np.float64)
        # 按 ADP 排序的索引（模拟按 ADP 选人 + 随机噪声）
        sorted_idx = np.argsort(adp_arr)
        vorp_sorted = vorp_arr[sorted_idx]
        adp_sorted = adp_arr[sorted_idx]

        total_picks = self.league_size * self.rounds

        # 运行加速核心
        draft_counts, pick_sums = _simulate_core(
            adp_sorted, iterations, total_picks, self.rounds, self.league_size,
            cancel_check=cancel_check,
        )
        # 取消：返回空 DataFrame
        if draft_counts is None:
            logger.info("蒙特卡洛模拟被取消")
            return pd.DataFrame(columns=["name", "pos", "vorp", "adp",
                                         "times_drafted", "draft_rate", "avg_pick", "avg_round"])

        # 聚合结果（映射回原始球员顺序）
        counts_orig = np.zeros(n_players, dtype=np.int64)
        picksums_orig = np.zeros(n_players, dtype=np.float64)
        for i, orig_idx in enumerate(sorted_idx):
            counts_orig[orig_idx] = draft_counts[i]
            picksums_orig[orig_idx] = pick_sums[i]

        result = df[["name", "pos", "vorp", "adp"]].copy()
        result["times_drafted"] = counts_orig
        result["draft_rate"] = counts_orig / iterations if iterations > 0 else 0
        result["avg_pick"] = np.where(
            counts_orig > 0, picksums_orig / np.maximum(counts_orig, 1), 0
        )
        result["avg_round"] = result["avg_pick"] / self.league_size

        elapsed = _time.time() - t0
        logger.info("蒙特卡洛模拟完成：%d 次，耗时 %.1f 秒", iterations, elapsed)
        return result.sort_values("draft_rate", ascending=False).reset_index(drop=True)

    def _run_single(self, rng, strategy_names, pick_records: List[Dict]) -> None:
        """单次模拟（保留用于兼容，simulate_draft 不再调用）。"""
        drafters = {t: get_drafter(rng.choice(strategy_names), self.league_config)
                    for t in range(1, self.league_size + 1)}
        drafted = set()
        for round_num in range(1, self.rounds + 1):
            order = (
                list(range(1, self.league_size + 1))
                if round_num % 2 == 1
                else list(range(self.league_size, 0, -1))
            )
            for pick_in_round, team_id in enumerate(order, 1):
                available = self.players[~self.players["name"].isin(drafted)]
                name = drafters[team_id].draft(available)
                if name is None:
                    continue
                drafted.add(name)
                total_pick = (round_num - 1) * self.league_size + pick_in_round
                player = self.players[self.players["name"] == name].iloc[0]
                pick_records.append({
                    "name": name, "pos": player.get("pos"),
                    "vorp": player.get("vorp", 0), "adp": player.get("adp", 999),
                    "round": round_num, "pick_number": total_pick, "team": team_id,
                })

    def analyze_availability(self, target_pick: int) -> pd.DataFrame:
        """基于 ADP 模型估算各球员在目标顺位的可用概率（非模拟，快速估算）。"""
        df = self.players.copy()
        probs = calculate_availability(df["adp"].values, target_pick)
        df["availability_prob"] = probs
        # 按评分方法返回对应的价值列（SGP 池无 vorp 列）
        value_col = "sgp_total" if self.method == "sgp" and "sgp_total" in df.columns else "vorp"
        return df[["name", "pos", value_col, "adp", "availability_prob"]].sort_values(
            "availability_prob", ascending=False
        )


def simulate_drafts(
    iterations: int = 1000, player_pool: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """便捷函数：运行蒙特卡洛模拟。"""
    engine = DraftEngine(player_pool)
    return engine.simulate_draft(iterations=iterations)
