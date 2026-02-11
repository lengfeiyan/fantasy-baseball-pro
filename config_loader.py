#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载工具
负责读取和验证config.yaml配置文件
"""

import os
import yaml
from typing import Dict, Any, Optional


class ConfigLoader:
    """配置加载器类"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 验证配置
        self._validate_config()
        
        return self.config
    
    def _validate_config(self) -> None:
        """
        验证配置文件的完整性和正确性
        
        Raises:
            ValueError: 配置无效
        """
        if not self.config:
            raise ValueError("配置文件为空")
        
        # 验证数据配置
        self._validate_data_config()
        
        # 验证预测源配置
        self._validate_projections_config()
        
        # 验证联盟配置
        self._validate_league_config()
        
        # 验证选秀模拟器配置
        self._validate_draft_simulator_config()
        
        # 验证风险模型配置
        self._validate_risk_model_config()
        
        # 验证日志配置
        self._validate_logging_config()
    
    def _validate_data_config(self) -> None:
        """验证数据配置"""
        data_config = self.config.get('data', {})
        
        # 验证use_multi_source
        if 'use_multi_source' not in data_config:
            data_config['use_multi_source'] = False
        
        # 验证file_patterns
        if 'file_patterns' not in data_config:
            data_config['file_patterns'] = {
                'hitters': 'hitters_2026.csv',
                'pitchers': 'pitchers_2026.csv'
            }
        
        # 验证positions_file
        if 'positions_file' not in data_config:
            data_config['positions_file'] = 'data/player_positions_2025.csv'
    
    def _validate_projections_config(self) -> None:
        """验证预测源配置"""
        projections_config = self.config.get('projections', {})
        
        # 验证weights
        weights = projections_config.get('weights', {})
        if not weights:
            weights['STEAMER'] = 1.0
        
        # 验证权重总和为1.0
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"预测源权重总和必须为1.0，当前为{total_weight}")
        
        # 验证sources
        if 'sources' not in projections_config:
            projections_config['sources'] = list(weights.keys())
    
    def _validate_league_config(self) -> None:
        """验证联盟配置"""
        league_config = self.config.get('league', {})
        
        # 验证size
        if 'size' not in league_config:
            league_config['size'] = 12
        
        # 验证rounds
        if 'rounds' not in league_config:
            league_config['rounds'] = 15
        
        # 验证roster_slots
        if 'roster_slots' not in league_config:
            league_config['roster_slots'] = {
                'C': 1,
                '1B': 1,
                '2B': 1,
                '3B': 1,
                'SS': 1,
                'OF': 4,
                'SP': 4,
                'RP': 3,
                'UTIL': 1
            }
        
        # 验证scoring
        if 'scoring' not in league_config:
            league_config['scoring'] = {
                'hitters': {
                    'R': 1,
                    'HR': 1,
                    'RBI': 1,
                    'SB': 1,
                    'AVG': 1
                },
                'pitchers': {
                    'W': 1,
                    'SV': 1,
                    'HOLD': 1,
                    'ERA': -1,
                    'WHIP': -1,
                    'K_per_9': 1
                }
            }
    
    def _validate_draft_simulator_config(self) -> None:
        """验证选秀模拟器配置"""
        draft_config = self.config.get('draft_simulator', {})
        
        # 验证default_strategy
        if 'default_strategy' not in draft_config:
            draft_config['default_strategy'] = 'balanced'
        else:
            strategy = draft_config['default_strategy']
            if strategy not in ['conservative', 'balanced', 'aggressive']:
                raise ValueError(f"无效的选秀策略: {strategy}，必须是 conservative/balanced/aggressive")
        
        # 验证show_value_picks
        if 'show_value_picks' not in draft_config:
            draft_config['show_value_picks'] = True
        
        # 验证adp_file
        if 'adp_file' not in draft_config:
            draft_config['adp_file'] = 'adp.csv'
    
    def _validate_risk_model_config(self) -> None:
        """验证风险模型配置"""
        risk_config = self.config.get('risk_model', {})
        
        # 验证method
        if 'method' not in risk_config:
            risk_config['method'] = 'z_score'
        else:
            method = risk_config['method']
            if method not in ['z_score', 'historical_variance']:
                raise ValueError(f"无效的风险计算方法: {method}，必须是 z_score/historical_variance")
        
        # 验证adjustment_factor
        if 'adjustment_factor' not in risk_config:
            risk_config['adjustment_factor'] = 0.1
    
    def _validate_logging_config(self) -> None:
        """验证日志配置"""
        logging_config = self.config.get('logging', {})
        
        # 验证level
        if 'level' not in logging_config:
            logging_config['level'] = 'INFO'
        else:
            level = logging_config['level']
            if level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                raise ValueError(f"无效的日志级别: {level}，必须是 DEBUG/INFO/WARNING/ERROR")
        
        # 验证file
        if 'file' not in logging_config:
            logging_config['file'] = 'fantasy_baseball.log'


# 全局配置实例
config_loader = ConfigLoader()


def get_config() -> Dict[str, Any]:
    """
    获取配置
    
    Returns:
        配置字典
    """
    if not config_loader.config:
        config_loader.load()
    return config_loader.config
