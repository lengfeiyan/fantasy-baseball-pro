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
import datetime
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .utils.logger import PROJECT_ROOT, get_logger

logger = get_logger("config")

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


def current_season() -> int:
    """当前赛季年份（按日历年）。修复 H7：不再硬编码 2026。"""
    return datetime.date.today().year

# 集中定义所有默认值（消除旧版散落在 6 个 _validate_* 方法里的默认值漂移）
DEFAULTS: Dict[str, Any] = {
    "data": {
        "season": current_season(),
        "use_multi_source": False,
        "file_patterns": {
            "hitters": "hitters_{season}_{source}.csv",
            "pitchers": "pitchers_{season}_{source}.csv",
        },
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


def get_season(config: Optional[Dict[str, Any]] = None) -> int:
    """返回生效的赛季年份（修复 H7：统一从配置读取，默认当前年）。

    Args:
        config: 已加载的配置 dict；None 则取 get_config()。

    Returns:
        赛季年份 int。
    """
    cfg = config or get_config()
    try:
        return int(cfg.get("data", {}).get("season") or current_season())
    except (TypeError, ValueError):
        return current_season()


def resolve_path(relative_path: str) -> str:
    """将相对路径解析为相对项目根的绝对路径。已是绝对路径则原样返回。"""
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(PROJECT_ROOT, relative_path)


def output_path(filename: str) -> str:
    """把输出文件放入统一的 output/ 目录（自动创建）。

    修复 M8：此前排名 CSV/选秀日志/FA 导出全部散落在项目根目录，
    且同名文件静默覆盖。统一收进 output/ 子目录。

    Args:
        filename: 文件名（不含目录部分；若含则只取文件名）。

    Returns:
        output/<filename> 的绝对路径，目录已确保存在。
    """
    out_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, os.path.basename(filename))


# history_path 进程内同毫秒去重（CI 快机器上连续两次调用可落在同一毫秒）
_hist_last_stamp = ""
_hist_seq = 0


def history_path(filename: str) -> str:
    """生成带时间戳的历史备份路径：output/history/<名>_<时间戳>.csv。

    数据统一入库后，CSV 从"最新数据"降级为"历史快照"：每次生成写一个
    时间戳文件，不再覆盖；DB 始终保存当前状态。

    审计修复：时间戳含毫秒 + 已存在时追加序号——同秒两次生成不再
    静默覆盖（与「永不覆盖」的承诺一致）。CI 实测快机器上连续调用可
    落在同一毫秒，进程内再用递增序号兜底。
    """
    global _hist_last_stamp, _hist_seq
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
    if stamp == _hist_last_stamp:
        _hist_seq += 1
        stamp = f"{stamp}_{_hist_seq}"
    else:
        _hist_last_stamp = stamp
        _hist_seq = 0
    base = os.path.basename(filename)
    stem = base[:-4] if base.lower().endswith(".csv") else base
    history_dir = os.path.join(PROJECT_ROOT, "output", "history")
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, f"{stem}_{stamp}.csv")
    seq = 1
    while os.path.exists(path):
        path = os.path.join(history_dir, f"{stem}_{stamp}_{seq}.csv")
        seq += 1
    return path


def write_csv_atomic(path: str, df) -> None:
    """把 DataFrame 原子写入 CSV（temp + os.replace）。

    审计修复：「最近一份」CSV 是固定路径、可能被并发任务同时写，
    直接 to_csv 在 Windows 上会交错产生损坏文件；先写临时文件再
    原子替换，读者只会看到完整的新版或旧版。
    """
    import uuid

    tmp = f"{path}.tmp.{uuid.uuid4().hex[:8]}"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def find_output_file(filename: str) -> str:
    """定位输出/数据文件：优先 output/ 目录，其次项目根（兼容旧文件）。

    Args:
        filename: 绝对路径原样返回；带目录的相对路径按 resolve_path 处理；
            纯文件名先在 output/ 下找，找不到再回落项目根。

    Returns:
        存在的文件路径；都不存在时返回 output/ 下的路径（供写操作使用）。
    """
    if os.path.isabs(filename):
        return filename
    if os.path.dirname(filename):
        return resolve_path(filename)
    in_output = output_path(filename)
    if os.path.exists(in_output):
        return in_output
    legacy = resolve_path(filename)
    if os.path.exists(legacy):
        return legacy
    return in_output


def _index_config_line_paths(lines: List[str]) -> Dict[int, str]:
    """给配置文件的每个「键定义行」标注完整点分路径。

    通过缩进栈推断层级（不依赖固定 2 空格约定）；列表项（``- `` 开头）、
    空行、注释行不定义键。返回 ``{行号: "a.b.c"}``。
    """
    result: Dict[int, str] = {}
    stack: List[Tuple[int, str]] = []  # [(缩进列数, 键名)]
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        m = re.match(r"^([\w\-\.]+)\s*:", stripped)
        if not m:
            continue
        key = m.group(1)
        indent = len(line) - len(stripped)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        result[i] = ".".join(k for _, k in stack)
    return result


def save_config_values(updates: Dict[str, Any]) -> List[str]:
    """更新 config.yaml 中指定路径的值，保留注释和原有结构。

    用逐行文本替换而非 yaml.safe_dump，确保用户的注释不丢失。

    修复审计高危项：旧实现只按「key 名 + 缩进」匹配行、first-match-wins，
    不区分所在段落——``league.scoring.hitters.R`` 与
    ``sgp.denominators.hitters.R`` 同名同缩进（6 空格），league 段在文件前面，
    SGP 分母的更新会把 league 评分权重行改写（R: 1 → 24.6）。
    现按行的完整点分路径精确匹配。

    Args:
        updates: 点分路径 → 新值。如 {"league.size": 14, "league.scoring.hitters.HR": 2}

    Returns:
        未在文件中找到对应行的路径列表（调用方可据此提示用户），全部命中时为空。
    """
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    line_paths = _index_config_line_paths(lines)
    unmatched: List[str] = []
    for path, value in updates.items():
        target = next((i for i, dotted in line_paths.items() if dotted == path), None)
        if target is None:
            unmatched.append(path)
            continue

        line = lines[target]
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        final_key = path.split(".")[-1]
        # 保留行尾注释。YAML 约定 # 前须有空格才构成注释；且要求切分点
        # 之前引号成对（引号内的 " #" 属于值本身，不是注释——审计低危项）。
        comment = ""
        pos = -1
        for i in range(len(line) - 1):
            if line[i] == " " and line[i + 1] == "#":
                if line[:i].count('"') % 2 == 0:
                    pos = i
                    break
        if pos >= 0:
            comment = "  " + line[pos:].rstrip()

        # 格式化新值（字符串转义引号与反斜杠，防止写出非法 YAML）
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            formatted = f'{final_key}: "{escaped}"'
        elif isinstance(value, bool):
            formatted = f"{final_key}: {str(value).lower()}"
        else:
            formatted = f"{final_key}: {value}"
        lines[target] = f"{indent}{formatted}{comment}\n"

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    if unmatched:
        logger.warning("以下配置路径在 config.yaml 中未找到，未更新: %s", unmatched)

    # 失效缓存
    global _cache
    _cache = None
    return unmatched
