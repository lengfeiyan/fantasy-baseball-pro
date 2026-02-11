#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 经理人策略模块
定义不同类型的AI经理人及其选秀策略
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple


class BaseDrafter:
    """基础经理人策略类"""
    
    def __init__(self, league_config: Dict):
        """
        初始化经理人
        
        Args:
            league_config: 联盟配置
        """
        self.league_config = league_config
        self.roster = {}
        self.picks = []
    
    def reset(self):
        """
        重置经理人状态
        """
        self.roster = {}
        self.picks = []
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 基础策略：选择VORP最高的球员
        best_player = available_players.nlargest(1, 'vorp')
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name
    
    def get_roster_needs(self) -> Dict[str, int]:
        """
        获取阵容需求
        
        Returns:
            各位置的需求数量
        """
        needs = {}
        roster_slots = self.league_config['roster_slots']
        
        for pos, max_count in roster_slots.items():
            current_count = len(self.roster.get(pos, []))
            needs[pos] = max(0, max_count - current_count)
        
        return needs


class BalancedDrafter(BaseDrafter):
    """均衡型经理人策略"""
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 获取阵容需求
        needs = self.get_roster_needs()
        
        # 计算位置优先级（基于需求和位置价值）
        pos_value = {
            'C': 1.2, 'SS': 1.1, '2B': 1.05, '3B': 1.0, 
            '1B': 0.9, 'OF': 0.95, 'SP': 1.15, 'RP': 0.8
        }
        
        # 为每个球员计算优先级分数
        def calculate_priority(row):
            pos = row['pos']
            need = needs.get(pos, 0)
            value = pos_value.get(pos, 1.0)
            
            # 需求越高，优先级越高
            need_factor = 1.0 + (need * 0.3)
            
            return row['vorp'] * value * need_factor
        
        # 应用优先级计算
        available_players['priority'] = available_players.apply(calculate_priority, axis=1)
        best_player = available_players.nlargest(1, 'priority')
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name


class PositionalHoarderDrafter(BaseDrafter):
    """位置囤积型经理人策略"""
    
    def __init__(self, league_config: Dict):
        """
        初始化经理人
        
        Args:
            league_config: 联盟配置
        """
        super().__init__(league_config)
        # 优先囤积的位置
        self.priority_positions = ['SP', 'SS', 'C']
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 获取阵容需求
        needs = self.get_roster_needs()
        
        # 优先选择优先级位置的球员
        priority_players = available_players[available_players['pos'].isin(self.priority_positions)]
        
        if not priority_players.empty:
            # 为优先级位置球员计算分数
            def calculate_priority(row):
                pos = row['pos']
                need = needs.get(pos, 0)
                
                # 优先级位置加成
                priority_bonus = 1.5 if pos in self.priority_positions else 1.0
                need_factor = 1.0 + (need * 0.4)
                
                return row['vorp'] * priority_bonus * need_factor
            
            priority_players['priority'] = priority_players.apply(calculate_priority, axis=1)
            best_player = priority_players.nlargest(1, 'priority')
        else:
            # 没有优先级位置球员，选择VORP最高的
            best_player = available_players.nlargest(1, 'vorp')
        
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name


class StatcastBelieverDrafter(BaseDrafter):
    """Statcast信徒经理人策略"""
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 检查是否有Statcast数据
        has_statcast = 'xwoba' in available_players.columns or 'xera' in available_players.columns
        
        if has_statcast:
            # 为球员计算Statcast调整后的分数
            def calculate_statcast_score(row):
                base_score = row['vorp']
                
                # 打者Statcast调整
                if 'xwoba' in row and pd.notna(row['xwoba']):
                    if row['xwoba'] >= 0.34:
                        base_score *= 1.2
                    elif row['xwoba'] >= 0.32:
                        base_score *= 1.1
                
                # 投手Statcast调整
                if 'xera' in row and pd.notna(row['xera']):
                    if row['xera'] <= 3.5:
                        base_score *= 1.2
                    elif row['xera'] <= 4.0:
                        base_score *= 1.1
                
                return base_score
            
            available_players['statcast_score'] = available_players.apply(calculate_statcast_score, axis=1)
            best_player = available_players.nlargest(1, 'statcast_score')
        else:
            # 没有Statcast数据，使用基础策略
            best_player = available_players.nlargest(1, 'vorp')
        
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name


class ADPFollowerDrafter(BaseDrafter):
    """ADP跟随者经理人策略"""
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 检查是否有ADP数据
        if 'adp' in available_players.columns:
            # 选择ADP最低（即排名最高）的球员
            best_player = available_players.nsmallest(1, 'adp')
        else:
            # 没有ADP数据，使用基础策略
            best_player = available_players.nlargest(1, 'vorp')
        
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name


class YourStrategyDrafter(BaseDrafter):
    """你的个人策略经理人"""
    
    def draft(self, available_players: pd.DataFrame) -> Optional[str]:
        """
        执行选秀
        
        Args:
            available_players: 可用球员数据
            
        Returns:
            选中的球员名称
        """
        if available_players.empty:
            return None
        
        # 根据选秀轮次调整策略
        round_num = len(self.picks) + 1
        
        if round_num <= 3:
            # 前3轮：只考虑先发投手（SP）
            sp_players = available_players[available_players['pos'] == 'SP']
            if not sp_players.empty:
                best_player = sp_players.nlargest(1, 'vorp')
            else:
                # 没有SP，选择VORP最高的球员
                best_player = available_players.nlargest(1, 'vorp')
        elif 4 <= round_num <= 8:
            # 4-8轮：锁定≤25岁高VORP打者
            if 'age' in available_players.columns:
                young_hitters = available_players[
                    (available_players['age'] <= 25) & 
                    (available_players['pos'].isin(['C', '1B', '2B', '3B', 'SS', 'OF']))
                ]
                if not young_hitters.empty:
                    best_player = young_hitters.nlargest(1, 'vorp')
                else:
                    # 没有符合条件的年轻打者，选择VORP最高的球员
                    best_player = available_players.nlargest(1, 'vorp')
            else:
                # 没有年龄数据，选择VORP最高的球员
                best_player = available_players.nlargest(1, 'vorp')
        else:
            # 9+轮：专注Statcast信号
            if 'xwoba' in available_players.columns or 'xera' in available_players.columns:
                def calculate_statcast_score(row):
                    base_score = row['vorp']
                    
                    # 打者Statcast调整
                    if 'xwoba' in row and pd.notna(row['xwoba']):
                        if row['xwoba'] >= 0.34:
                            base_score *= 1.3
                        elif row['xwoba'] >= 0.32:
                            base_score *= 1.15
                    
                    # 投手Statcast调整
                    if 'xera' in row and pd.notna(row['xera']):
                        if row['xera'] <= 3.5:
                            base_score *= 1.3
                        elif row['xera'] <= 4.0:
                            base_score *= 1.15
                    
                    return base_score
                
                available_players['statcast_score'] = available_players.apply(calculate_statcast_score, axis=1)
                best_player = available_players.nlargest(1, 'statcast_score')
            else:
                # 没有Statcast数据，选择VORP最高的球员
                best_player = available_players.nlargest(1, 'vorp')
        
        player_name = best_player.iloc[0]['name']
        
        # 更新阵容
        pos = best_player.iloc[0]['pos']
        if pos not in self.roster:
            self.roster[pos] = []
        self.roster[pos].append(player_name)
        self.picks.append(player_name)
        
        return player_name


# 为每个 drafter 类添加 calculate_value 方法
BaseDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: available_players['vorp']

BalancedDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: \
    available_players['vorp'] * available_players['position'].apply(lambda pos: \
        (1.2 if pos == 'C' else 1.1 if pos == 'SS' else 1.05 if pos == '2B' else \
         1.0 if pos == '3B' else 0.9 if pos == '1B' else 0.95 if pos == 'OF' else \
         1.15 if pos == 'SP' else 0.8 if pos == 'RP' else 1.0))

PositionalHoarderDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: \
    available_players['vorp'] * available_players['position'].apply(lambda pos: \
        1.5 if pos in ['SP', 'SS', 'C'] else 1.0)

StatcastBelieverDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: \
    available_players['vorp']

ADPFollowerDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: \
    available_players['vorp'] * (1000 - available_players.get('adp', 999)) / 1000 if 'adp' in available_players.columns else available_players['vorp']

YourStrategyDrafter.calculate_value = lambda self, available_players, current_roster, roster_slots, pick_num, total_picks: \
    available_players['vorp']


def get_drafter(strategy_name, config):
    """根据策略名称获取对应的 drafter 实例"""
    drafter_map = {
        'balanced': BalancedDrafter,
        'positional_hoarder': PositionalHoarderDrafter,
        'statcast_believer': StatcastBelieverDrafter,
        'adp_follower': ADPFollowerDrafter,
        'your_strategy': YourStrategyDrafter
    }
    
    drafter_class = drafter_map.get(strategy_name, BalancedDrafter)
    return drafter_class(config)