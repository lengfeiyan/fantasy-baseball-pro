"""配置加载测试。"""

from __future__ import annotations

import os

import pytest
import yaml

from fantasy_baseball.config import DEFAULTS, _deep_merge, _validate, get_config


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
