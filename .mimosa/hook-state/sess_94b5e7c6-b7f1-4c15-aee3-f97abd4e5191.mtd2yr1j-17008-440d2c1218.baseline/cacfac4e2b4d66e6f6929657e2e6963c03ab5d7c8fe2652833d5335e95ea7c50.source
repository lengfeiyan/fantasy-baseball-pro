#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VORP 计算器模块
负责计算球员的 Value Over Replacement Player
整合 Statcast 数据和传统统计数据
"""

import pandas as pd
from typing import Dict, Any, Optional


class VORPCalculator:
    """VORP 计算器"""
    
    def __init__(self, replacement_levels: Optional[Dict[str, float]] = None):
        """
        初始化 VORP 计算器
        
        Args:
            replacement_levels: 各位置的替代水平值
        """
        # 默认替代水平值
        self.default_replacement_levels = {
            'C': 30,    # 捕手替代水平
            '1B': 40,   # 一垒手替代水平
            '2B': 35,   # 二垒手替代水平
            '3B': 35,   # 三垒手替代水平
            'SS': 30,   # 游击手替代水平
            'OF': 35,   # 外野手替代水平
            'SP': 35,   # 先发投手替代水平
            'RP': 25,   # 中继投手替代水平
            'UTIL': 35  # 工具人替代水平
        }
        
        self.replacement_levels = replacement_levels or self.default_replacement_levels
    
    def calculate_vorp(self, player_stats: pd.DataFrame, position: str) -> float:
        """
        计算单个球员的 VORP
        
        Args:
            player_stats: 球员统计数据
            position: 球员位置
            
        Returns:
            float: VORP 值
        """
        # 获取替代水平
        replacement_level = self.replacement_levels.get(position, 35)
        
        # 计算基础 VORP
        fantasy_points = player_stats.get('fantasy_points', 0)
        base_vorp = fantasy_points - replacement_level
        
        # 整合 Statcast 数据
        statcast_boost = self._calculate_statcast_boost(player_stats, position)
        
        # 计算最终 VORP
        final_vorp = base_vorp + statcast_boost
        
        return max(0, final_vorp)  # VORP 不能为负
    
    def _calculate_statcast_boost(self, player_stats: pd.DataFrame, position: str) -> float:
        """
        计算 Statcast 数据带来的 VORP 提升
        
        Args:
            player_stats: 球员统计数据
            position: 球员位置
            
        Returns:
            float: Statcast 提升值
        """
        boost = 0.0
        
        if position in ['C', '1B', '2B', '3B', 'SS', 'OF']:
            # 打者 Statcast 提升
            # xwOBA 提升
            if 'xwoba' in player_stats:
                xwoba = player_stats['xwoba']
                if xwoba > 0.400:
                    boost += 15
                elif xwoba > 0.350:
                    boost += 10
                elif xwoba > 0.300:
                    boost += 5
            
            # exit velocity 提升
            if 'avg_exit_velocity' in player_stats:
                ev = player_stats['avg_exit_velocity']
                if ev > 95:
                    boost += 8
                elif ev > 90:
                    boost += 4
                elif ev > 85:
                    boost += 2
            
            # barrel rate 提升
            if 'barrel_rate' in player_stats:
                barrel_rate = player_stats['barrel_rate']
                if barrel_rate > 0.15:
                    boost += 6
                elif barrel_rate > 0.10:
                    boost += 3
                elif barrel_rate > 0.05:
                    boost += 1
        
        elif position in ['SP', 'RP']:
            # 投手 Statcast 提升
            # xwoba against 提升
            if 'xwoba_against' in player_stats:
                xwoba_against = player_stats['xwoba_against']
                if xwoba_against < 0.300:
                    boost += 10
                elif xwoba_against < 0.320:
                    boost += 5
                elif xwoba_against < 0.350:
                    boost += 2
            
            # strikeout probability 提升
            if 'avg_strikeout_prob' in player_stats:
                k_prob = player_stats['avg_strikeout_prob']
                if k_prob > 0.30:
                    boost += 8
                elif k_prob > 0.25:
                    boost += 4
                elif k_prob > 0.20:
                    boost += 2
        
        return boost
    
    def calculate_team_vorp(self, team_roster: pd.DataFrame) -> float:
        """
        计算球队整体 VORP
        
        Args:
            team_roster: 球队阵容
            
        Returns:
            float: 球队整体 VORP
        """
        total_vorp = 0
        
        for idx, player in team_roster.iterrows():
            position = player.get('position', 'UTIL')
            vorp = player.get('vorp', 0)
            total_vorp += vorp
        
        return total_vorp
    
    def calculate_all_players_vorp(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        计算球员池中所有球员的 VORP
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 包含 VORP 的球员池
        """
        # 复制球员池
        vorp_pool = player_pool.copy()
        
        # 添加 VORP 列
        if 'vorp' not in vorp_pool.columns:
            vorp_pool['vorp'] = 0
        
        # 遍历球员，计算 VORP
        for idx, player in vorp_pool.iterrows():
            position = player.get('position', 'UTIL')
            vorp = self.calculate_vorp(player, position)
            vorp_pool.at[idx, 'vorp'] = vorp
        
        return vorp_pool
