"""配置加载测试。"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest
import yaml

from fantasy_baseball import config as config_mod
from fantasy_baseball.config import (
    DEFAULTS,
    _deep_merge,
    _validate,
    get_config,
    save_config_values,
)


def test_get_config_returns_dict():
    cfg = get_config()
    assert isinstance(cfg, dict)
    assert "league" in cfg
    assert "scoring" in cfg["league"]


def test_get_config_returns_copy():
    """修改返回值不应污染单例缓存。"""
    cfg1 = get_config()
    cfg1["league"]["size"] = 999
    cfg2 = get_config()
    assert cfg2["league"]["size"] != 999


def test_default_values_present():
    cfg = get_config()
    for section in ("data", "projections", "league", "draft_simulator",
                    "risk_model", "logging", "fa_analyzer"):
        assert section in cfg, f"缺少默认段: {section}"


def test_deep_merge_override_wins():
    base = {"a": {"b": 1, "c": 2}, "x": 10}
    override = {"a": {"b": 99}, "y": 20}
    result = _deep_merge(base, override)
    assert result == {"a": {"b": 99, "c": 2}, "x": 10, "y": 20}


def test_deep_merge_nested_dicts():
    base = {"l": {"r": {"s": 1}}}
    override = {"l": {"r": {"t": 2}}}
    result = _deep_merge(base, override)
    assert result["l"]["r"] == {"s": 1, "t": 2}


def test_validate_rejects_bad_weights():
    cfg = {"projections": {"weights": {"A": 0.5, "B": 0.2}}}  # 和=0.7
    with pytest.raises(ValueError, match="权重"):
        _validate(cfg)


def test_validate_rejects_bad_strategy():
    cfg = {"projections": {"weights": {"A": 1.0}},
           "draft_simulator": {"default_strategy": "invalid"}}
    with pytest.raises(ValueError, match="策略"):
        _validate(cfg)


def test_validate_rejects_bad_risk_method():
    cfg = {"projections": {"weights": {"A": 1.0}},
           "draft_simulator": {"default_strategy": "balanced"},
           "risk_model": {"method": "bogus"}}
    with pytest.raises(ValueError, match="风险"):
        _validate(cfg)


def test_validate_rejects_bad_log_level():
    cfg = {"projections": {"weights": {"A": 1.0}},
           "draft_simulator": {"default_strategy": "balanced"},
           "risk_model": {"method": "z_score"},
           "logging": {"level": "TRACE"}}
    with pytest.raises(ValueError, match="日志级别"):
        _validate(cfg)


# ============================================================
# save_config_values（在临时副本上测试，不动真实 config.yaml）
# ============================================================
@pytest.fixture
def tmp_config(tmpdir, monkeypatch):
    """把模块 CONFIG_PATH 指向真实 config.yaml 的临时副本。"""
    src = os.path.join(config_mod.PROJECT_ROOT, "config.yaml")
    dst = str(tmpdir.join("config.yaml"))
    shutil.copy(src, dst)
    monkeypatch.setattr(config_mod, "CONFIG_PATH", dst)
    return dst


def test_save_no_cross_section_overwrite(tmp_config):
    """回归（审计高危）：同名同缩进的跨段 key 不得互相覆盖。

    旧实现按「key 名 + 缩进」first-match 匹配，sgp.denominators.hitters.R
    会把 league 段在前面的 R 行（评分权重）改写成 SGP 分母值。
    """
    unmatched = save_config_values({
        "league.scoring.hitters.R": 1.0,
        "league.scoring.hitters.HR": 1.0,
        "sgp.denominators.hitters.R": 24.6,
        "sgp.denominators.hitters.HR": 10.4,
    })
    assert unmatched == []

    result = yaml.safe_load(open(tmp_config, encoding="utf-8"))
    lg = result["league"]["scoring"]["hitters"]
    sg = result["sgp"]["denominators"]["hitters"]
    assert lg["R"] == 1.0
    assert lg["HR"] == 1.0
    assert sg["R"] == 24.6
    assert sg["HR"] == 10.4


def test_save_pitcher_sections_no_overwrite(tmp_config):
    """投手侧同名 key（W/SV/ERA/WHIP 在两段都有）同样不得串写。"""
    save_config_values({
        "league.scoring.pitchers.ERA": -1,
        "sgp.denominators.pitchers.ERA": -0.076,
    })
    result = yaml.safe_load(open(tmp_config, encoding="utf-8"))
    assert result["league"]["scoring"]["pitchers"]["ERA"] == -1
    assert result["sgp"]["denominators"]["pitchers"]["ERA"] == -0.076


def test_save_preserves_comments_and_values(tmp_config):
    """注释保留 + 常规更新 + 布尔/字符串格式化。"""
    save_config_values({
        "league.size": 14,
        "draft_simulator.default_strategy": "aggressive",
        "draft_simulator.show_value_picks": False,
    })
    text = open(tmp_config, encoding="utf-8").read()
    result = yaml.safe_load(text)
    assert result["league"]["size"] == 14
    assert result["draft_simulator"]["default_strategy"] == "aggressive"
    assert result["draft_simulator"]["show_value_picks"] is False
    assert "# 联盟规模" in text  # 注释仍在
    # 布尔必须是合法 YAML 字面量
    assert "show_value_picks: false" in text


def test_save_reports_unmatched_paths(tmp_config):
    """文件中不存在的路径：不写入、不崩溃，返回未命中列表。"""
    unmatched = save_config_values({
        "league.size": 12,
        "league.nonexistent.key": 1,
    })
    assert unmatched == ["league.nonexistent.key"]
    result = yaml.safe_load(open(tmp_config, encoding="utf-8"))
    assert result["league"]["size"] == 12


def test_save_invalidates_cache(tmp_config, monkeypatch):
    """保存后 get_config 必须重新读盘。"""
    before = get_config()["league"]["size"]
    save_config_values({"league.size": before + 1})
    assert get_config()["league"]["size"] == before + 1
