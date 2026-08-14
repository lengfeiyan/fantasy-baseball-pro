"""统一配置加载。

合并旧的 ``config_loader.py`` 与 ``utils/config_manager.py``，提供单一入口
``get_config()``。配置文件路径相对项目根解析，不再依赖调用方的工作目录。

特点：
- 首次调用读取磁盘，之后返回缓存（懒加载单例）。
- 缺失字段自动补默认值（深度合并，保留用户显式设置）。
- 权重和、策略名、风险方法、日志级别等做校验，非法值抛 ``ValueError``。
- 返回深拷贝，防止调用方污染单例。
"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional

import yaml

from .utils.logger import PROJECT_ROOT, get_logger

logger = get_logger("config")

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

# 集中定义所有默认值（消除旧版散落在 6 个 _validate_* 方法里的默认值漂移）
DEFAULTS: Dict[str, Any] = {
    "data": {
        "use_multi_source": False,
        "file_patterns": {"hitters": "hitters_2026.csv", "pitchers": "pitchers_2026.csv"},
        "positions_file": "data/player_positions_2025.csv",
    },
    "projections": {
        "weights": {"STEAMER": 1.0},
        "sources": ["STEAMER"],
    },
    "league": {
        "size": 12,
        "rounds": 15,
        "roster_slots": {
            "C": 1, "1B": 1, "2B": 1, "3B": 1, "SS": 1,
            "OF": 4, "SP": 4, "RP": 3, "UTIL": 1,
        },
        "scoring": {
            "hitters": {"R": 1, "HR": 1, "RBI": 1, "SB": 1, "AVG": 1},
            "pitchers": {"W": 1, "SV": 1, "HOLD": 1, "ERA": -1, "WHIP": -1, "K_per_9": 1},
        },
    },
    "draft_simulator": {
        "default_strategy": "balanced",
        "show_value_picks": True,
        "adp_file": "adp.csv",
    },
    "risk_model": {"method": "z_score", "adjustment_factor": 0.1},
    "scoring": {"stream_slots": 5},
    "logging": {"level": "INFO", "file": "fantasy_baseball.log"},
    "fa_analyzer": {
        "update_frequency": 6,
        "default_top_n": 10,
        "data_sources": ["MLB_API", "FANGRAPHS", "ESPN"],
        "algorithm": {
            "position_weight": 0.3,
            "performance_weight": 0.4,
            "risk_weight": 0.2,
            "opportunity_weight": 0.1,
        },
        "risk_model": {"default_preference": "balanced", "injury_weight": 0.3},
        "cache": {"expiry": 24, "directory": "data/cache"},
    },
    "sgp": {
        "denominators": {
            "hitters": {"R": 24.6, "HR": 10.4, "RBI": 24.6, "SB": 9.4, "AVG": 0.0024},
            "pitchers": {"W": 3.03, "SV": 9.95, "K": 39.3, "ERA": -0.076, "WHIP": -0.015},
        },
    },
}

_VALID_STRATEGIES = {"conservative", "balanced", "aggressive"}
_VALID_RISK_METHODS = {"z_score", "historical_variance"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 override 到 base，返回新 dict。override 中的值优先。"""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _validate(config: Dict[str, Any]) -> None:
    """校验配置合法性，非法值抛 ValueError。"""
    # 预测源权重必须和为 1.0
    weights = config.get("projections", {}).get("weights", {})
    if weights:
        total = sum(float(v) for v in weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"预测源权重总和必须为 1.0，当前为 {total}")

    strategy = config.get("draft_simulator", {}).get("default_strategy", "balanced")
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(
            f"无效的选秀策略: {strategy}，必须是 {sorted(_VALID_STRATEGIES)} 之一"
        )

    method = config.get("risk_model", {}).get("method", "z_score")
    if method not in _VALID_RISK_METHODS:
        raise ValueError(
            f"无效的风险计算方法: {method}，必须是 {sorted(_VALID_RISK_METHODS)} 之一"
        )

    level = config.get("logging", {}).get("level", "INFO")
    if level not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"无效的日志级别: {level}，必须是 {sorted(_VALID_LOG_LEVELS)} 之一"
        )


# 单例缓存
_cache: Optional[Dict[str, Any]] = None


def get_config(reload: bool = False) -> Dict[str, Any]:
    """获取合并默认值后的完整配置（深拷贝）。

    Args:
        reload: True 时强制重新从磁盘读取（用于测试或配置热更新）。

    Returns:
        配置字典的深拷贝，调用方可自由修改而不影响缓存。
    """
    global _cache
    if _cache is not None and not reload:
        return copy.deepcopy(_cache)

    if not os.path.exists(CONFIG_PATH):
        logger.warning("配置文件不存在: %s，使用纯默认配置", CONFIG_PATH)
        merged = copy.deepcopy(DEFAULTS)
    else:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        merged = _deep_merge(DEFAULTS, user_cfg)

    _validate(merged)
    _cache = merged
    logger.debug("配置加载完成")
    return copy.deepcopy(merged)


def get_db_path() -> str:
    """返回数据库文件的绝对路径（相对项目根）。"""
    return os.path.join(PROJECT_ROOT, "fantasy_baseball.db")


def resolve_path(relative_path: str) -> str:
    """将相对路径解析为相对项目根的绝对路径。已是绝对路径则原样返回。"""
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(PROJECT_ROOT, relative_path)


def save_config_values(updates: Dict[str, Any]) -> None:
    """更新 config.yaml 中指定路径的值，保留注释和原有结构。

    用逐行文本替换而非 yaml.safe_dump，确保用户的注释不丢失。

    Args:
        updates: 点分路径 → 新值。如 {"league.size": 14, "league.scoring.hitters.HR": 2}
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for path, value in updates.items():
        keys = path.split(".")
        final_key = keys[-1]
        # 计算目标缩进：每个层级 2 空格（YAML 惯例）
        target_indent = "  " * len(keys[:-1]) if len(keys) > 1 else ""

        for i, line in enumerate(lines):
            stripped = line.lstrip()
            # 匹配 "key:" 或 "key: value"
            if stripped.startswith(f"{final_key}:") or stripped.startswith(f"{final_key} :"):
                actual_indent = line[: len(line) - len(stripped)]
                if actual_indent == target_indent:
                    # 保留行尾注释（# 之后的部分）
                    comment = ""
                    comment_pos = line.find("#")
                    if comment_pos >= 0:
                        comment = "  " + line[comment_pos:].rstrip()

                    # 格式化新值
                    if isinstance(value, str):
                        formatted = f'{final_key}: "{value}"'
                    elif isinstance(value, bool):
                        formatted = f"{final_key}: {str(value).lower()}"
                    else:
                        formatted = f"{final_key}: {value}"
                    lines[i] = f"{target_indent}{formatted}{comment}\n"
                    break

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 失效缓存
    global _cache
    _cache = None
