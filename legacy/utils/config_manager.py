#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器
负责加载、验证和管理配置
支持分层配置和插件配置
"""

import os
import yaml
from typing import Dict, Any, Optional, List


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        初始化配置管理器
        
        Args:
            config_path: 主配置文件路径
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.defaults: Dict[str, Any] = self._load_defaults()
    
    def _load_defaults(self) -> Dict[str, Any]:
        """
        加载默认配置
        
        Returns:
            Dict[str, Any]: 默认配置
        """
        return {
            'data': {
                'use_multi_source': False,
                'file_patterns': {
                    'hitters': 'hitters_2026.csv',
                    'pitchers': 'pitchers_2026.csv'
                },
                'positions_file': 'data/player_positions_2025.csv'
            },
            'projections': {
                'weights': {
                    'STEAMER': 1.0
                },
                'sources': ['STEAMER']
            },
            'league': {
                'size': 12,
                'rounds': 15,
                'roster_slots': {
                    'C': 1,
                    '1B': 1,
                    '2B': 1,
                    '3B': 1,
                    'SS': 1,
                    'OF': 4,
                    'SP': 4,
                    'RP': 3,
                    'UTIL': 1
                },
                'scoring': {
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
            },
            'draft_simulator': {
                'default_strategy': 'balanced',
                'show_value_picks': True,
                'adp_file': 'adp.csv'
            },
            'risk_model': {
                'method': 'z_score',
                'adjustment_factor': 0.1
            },
            'logging': {
                'level': 'INFO',
                'file': 'fantasy_baseball.log'
            },
            'plugins': {
                'enabled': []
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        # 加载主配置文件
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                self.config = self._merge_configs(self.defaults, user_config)
        else:
            # 使用默认配置
            self.config = self.defaults.copy()
            # 保存默认配置到文件
            self.save_config()
        
        # 加载插件配置
        self._load_plugin_configs()
        
        return self.config
    
    def _merge_configs(self, defaults: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并默认配置和用户配置
        
        Args:
            defaults: 默认配置
            user_config: 用户配置
            
        Returns:
            Dict[str, Any]: 合并后的配置
        """
        merged = defaults.copy()
        
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # 递归合并字典
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # 直接覆盖
                merged[key] = value
        
        return merged
    
    def _load_plugin_configs(self) -> None:
        """
        加载插件配置
        """
        plugins_dir = 'plugins'
        if not os.path.exists(plugins_dir):
            return
        
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
            
            config_file = os.path.join(plugin_path, 'config.yaml')
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        plugin_config = yaml.safe_load(f)
                        if plugin_config:
                            self.plugin_configs[plugin_name] = plugin_config
                except Exception as e:
                    print(f"❌ 加载插件 {plugin_name} 配置失败: {e}")
    
    def save_config(self) -> None:
        """
        保存配置到文件
        """
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
    
    def get_config(self, section: Optional[str] = None) -> Any:
        """
        获取配置
        
        Args:
            section: 配置 section，None 表示获取完整配置
            
        Returns:
            Any: 配置值
        """
        if not section:
            return self.config
        
        # 支持嵌套 section，如 'league.roster_slots'
        parts = section.split('.')
        value = self.config
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value
    
    def get_plugin_config(self, plugin_name: str, section: Optional[str] = None) -> Any:
        """
        获取插件配置
        
        Args:
            plugin_name: 插件名称
            section: 配置 section，None 表示获取完整配置
            
        Returns:
            Any: 配置值
        """
        if plugin_name not in self.plugin_configs:
            return None
        
        if not section:
            return self.plugin_configs[plugin_name]
        
        # 支持嵌套 section
        parts = section.split('.')
        value = self.plugin_configs[plugin_name]
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value
    
    def update_config(self, section: str, value: Any) -> bool:
        """
        更新配置
        
        Args:
            section: 配置 section
            value: 配置值
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 支持嵌套 section
            parts = section.split('.')
            config = self.config
            
            # 遍历到倒数第二个 section
            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                config = config[part]
            
            # 更新值
            config[parts[-1]] = value
            
            # 保存配置
            self.save_config()
            return True
        except Exception:
            return False
    
    def validate_config(self) -> List[str]:
        """
        验证配置
        
        Returns:
            List[str]: 验证错误列表
        """
        errors = []
        
        # 验证预测源权重
        projections = self.config.get('projections', {})
        weights = projections.get('weights', {})
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"预测源权重总和必须为1.0，当前为{total_weight}")
        
        # 验证联盟配置
        league = self.config.get('league', {})
        if not isinstance(league.get('size'), int) or league['size'] <= 0:
            errors.append("联盟规模必须为正整数")
        
        if not isinstance(league.get('rounds'), int) or league['rounds'] <= 0:
            errors.append("选秀轮数必须为正整数")
        
        # 验证风险模型配置
        risk_model = self.config.get('risk_model', {})
        method = risk_model.get('method')
        if method not in ['z_score', 'historical_variance']:
            errors.append(f"无效的风险计算方法: {method}，必须是 z_score/historical_variance")
        
        # 验证日志配置
        logging = self.config.get('logging', {})
        level = logging.get('level')
        if level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            errors.append(f"无效的日志级别: {level}，必须是 DEBUG/INFO/WARNING/ERROR")
        
        return errors
