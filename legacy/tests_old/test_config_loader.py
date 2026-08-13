#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载器测试
"""

import os
import tempfile
import unittest
from config_loader import ConfigLoader, get_config


class TestConfigLoader(unittest.TestCase):
    """配置加载器测试类"""
    
    def setUp(self):
        """
        测试前准备
        """
        # 创建临时配置文件
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_config_path = self.temp_config.name
        
        # 写入测试配置
        test_config = """
data:
  use_multi_source: true
  file_patterns:
    hitters: "hitters_2026_{source}.csv"
    pitchers: "pitchers_2026_{source}.csv"
  positions_file: "data/player_positions_2025.csv"

projections:
  weights:
    STEAMER: 0.7
    ZIPS: 0.3
  sources:
    - STEAMER
    - ZIPS

league:
  size: 12
  rounds: 15
  roster_slots:
    C: 1
    1B: 1
    2B: 1
    3B: 1
    SS: 1
    OF: 4
    SP: 4
    RP: 3
    UTIL: 1
  scoring:
    hitters:
      R: 1
      HR: 1
      RBI: 1
      SB: 1
      AVG: 1
    pitchers:
      W: 1
      SV: 1
      HOLD: 1
      ERA: -1
      WHIP: -1
      K_per_9: 1

Draft_simulator:
  default_strategy: "balanced"
  show_value_picks: true
  adp_file: "adp.csv"

risk_model:
  method: "z_score"
  adjustment_factor: 0.1

logging:
  level: "INFO"
  file: "fantasy_baseball.log"
"""
        self.temp_config.write(test_config)
        self.temp_config.close()
    
    def tearDown(self):
        """
        测试后清理
        """
        # 删除临时配置文件
        if os.path.exists(self.temp_config_path):
            os.unlink(self.temp_config_path)
    
    def test_load_config(self):
        """
        测试加载配置文件
        """
        loader = ConfigLoader(self.temp_config_path)
        config = loader.load()
        
        # 验证配置加载成功
        self.assertIsNotNone(config)
        self.assertTrue(config['data']['use_multi_source'])
        self.assertEqual(config['projections']['weights']['STEAMER'], 0.7)
        self.assertEqual(config['league']['size'], 12)
        self.assertEqual(config['draft_simulator']['default_strategy'], 'balanced')
    
    def test_missing_config(self):
        """
        测试加载不存在的配置文件
        """
        loader = ConfigLoader('non_existent_config.yaml')
        with self.assertRaises(FileNotFoundError):
            loader.load()
    
    def test_invalid_weights(self):
        """
        测试无效的权重配置
        """
        # 创建权重总和不为1的配置文件
        invalid_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        invalid_config_path = invalid_config.name
        
        invalid_config_content = """
data:
  use_multi_source: true

projections:
  weights:
    STEAMER: 0.6
    ZIPS: 0.5
"""
        invalid_config.write(invalid_config_content)
        invalid_config.close()
        
        loader = ConfigLoader(invalid_config_path)
        with self.assertRaises(ValueError):
            loader.load()
        
        # 清理
        if os.path.exists(invalid_config_path):
            os.unlink(invalid_config_path)
    
    def test_invalid_strategy(self):
        """
        测试无效的选秀策略
        """
        # 创建包含无效策略的配置文件
        invalid_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        invalid_config_path = invalid_config.name
        
        invalid_config_content = """
draft_simulator:
  default_strategy: "invalid_strategy"
"""
        invalid_config.write(invalid_config_content)
        invalid_config.close()
        
        loader = ConfigLoader(invalid_config_path)
        with self.assertRaises(ValueError):
            loader.load()
        
        # 清理
        if os.path.exists(invalid_config_path):
            os.unlink(invalid_config_path)
    
    def test_get_config_singleton(self):
        """
        测试get_config函数的单例行为
        """
        # 第一次调用
        config1 = get_config()
        # 第二次调用
        config2 = get_config()
        
        # 验证返回的是同一个对象
        self.assertIs(config1, config2)


if __name__ == '__main__':
    unittest.main()
