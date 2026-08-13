#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心评估模块
整合 Statcast 数据、伤病风险分析和传统统计数据
为球员提供全面的价值评估
"""

import pandas as pd
from typing import Dict, Any, Optional
from .vorp_calculator import VORPCalculator
from .risk_analyzer import RiskAnalyzer
from data.statcast_data import StatcastFetcher
from data.injury_data import InjuryRiskModel


class CoreEvaluator:
    """核心评估器"""
    
    def __init__(self):
        """
        初始化核心评估器
        """
        # 初始化各个模块
        self.statcast_fetcher = StatcastFetcher()
        self.injury_risk_model = InjuryRiskModel()
        self.vorp_calculator = VORPCalculator()
        self.risk_analyzer = RiskAnalyzer(self.injury_risk_model)
    
    def evaluate_player(self, player_data: pd.DataFrame) -> Dict[str, Any]:
        """
        评估单个球员
        
        Args:
            player_data: 球员数据
            
        Returns:
            Dict[str, Any]: 评估结果
        """
        # 1. 整合 Statcast 数据
        enhanced_player = self.statcast_fetcher.integrate_with_player_pool(pd.DataFrame([player_data])).iloc[0]
        
        # 2. 计算 VORP
        position = enhanced_player.get('position', '')
        vorp = self.vorp_calculator.calculate_vorp(enhanced_player, position)
        enhanced_player['vorp'] = vorp
        
        # 3. 分析风险
        risk_analysis = self.risk_analyzer.analyze_player_risk(enhanced_player)
        
        # 4. 整合评估结果
        evaluation_result = {
            'player_id': enhanced_player.get('player_id', ''),
            'player_name': enhanced_player.get('player_name', ''),
            'position': position,
            'age': enhanced_player.get('age', 25),
            'vorp': vorp,
            'adjusted_value': risk_analysis['adjusted_value'],
            'injury_risk': risk_analysis['injury_risk'],
            'performance_risk': risk_analysis['performance_risk'],
            'total_risk': risk_analysis['total_risk'],
            'statcast_data': {
                'xwoba': enhanced_player.get('xwoba'),
                'avg_exit_velocity': enhanced_player.get('avg_exit_velocity'),
                'avg_launch_angle': enhanced_player.get('avg_launch_angle'),
                'barrel_rate': enhanced_player.get('barrel_rate'),
                'hard_hit_rate': enhanced_player.get('hard_hit_rate'),
                'exit_velocity_against': enhanced_player.get('exit_velocity_against'),
                'xwoba_against': enhanced_player.get('xwoba_against'),
                'avg_strikeout_prob': enhanced_player.get('avg_strikeout_prob'),
                'avg_walk_prob': enhanced_player.get('avg_walk_prob')
            }
        }
        
        return evaluation_result
    
    def evaluate_player_pool(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        评估球员池中的所有球员
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 包含评估结果的球员池
        """
        # 1. 整合 Statcast 数据
        statcast_pool = self.statcast_fetcher.integrate_with_player_pool(player_pool)
        
        # 2. 计算 VORP
        vorp_pool = self.vorp_calculator.calculate_all_players_vorp(statcast_pool)
        
        # 3. 分析风险
        evaluated_pool = self.risk_analyzer.analyze_all_players(vorp_pool)
        
        return evaluated_pool
    
    def generate_evaluation_report(self, player_pool: pd.DataFrame, sort_by: str = 'adjusted_value') -> pd.DataFrame:
        """
        生成评估报告
        
        Args:
            player_pool: 球员池数据
            sort_by: 排序字段
            
        Returns:
            pd.DataFrame: 评估报告
        """
        # 评估所有球员
        evaluated_pool = self.evaluate_player_pool(player_pool)
        
        # 选择关键列
        report_columns = [
            'player_id', 'player_name', 'position', 'age',
            'vorp', 'adjusted_value', 'injury_risk',
            'performance_risk', 'total_risk', 'xwoba',
            'avg_exit_velocity', 'barrel_rate'
        ]
        
        # 过滤列
        report = evaluated_pool[[col for col in report_columns if col in evaluated_pool.columns]]
        
        # 排序
        if sort_by in report.columns:
            report = report.sort_values(sort_by, ascending=False)
        
        return report
    
    def get_player_similarity(self, player_id: str, player_pool: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
        """
        查找与指定球员相似的球员
        
        Args:
            player_id: 球员 ID
            player_pool: 球员池数据
            top_n: 返回前 N 个相似球员
            
        Returns:
            pd.DataFrame: 相似球员列表
        """
        # 评估球员池
        evaluated_pool = self.evaluate_player_pool(player_pool)
        
        # 找到目标球员
        target_player = evaluated_pool[evaluated_pool['player_id'] == player_id]
        if target_player.empty:
            return pd.DataFrame()
        
        target_player = target_player.iloc[0]
        
        # 计算相似度
        def calculate_similarity(row):
            # 跳过自己
            if row['player_id'] == player_id:
                return -1
            
            # 位置相同的球员相似度更高
            position_similarity = 1.0 if row['position'] == target_player['position'] else 0.5
            
            # 年龄相似度
            age_diff = abs(row['age'] - target_player['age'])
            age_similarity = max(0, 1.0 - (age_diff / 10))
            
            # VORP 相似度
            vorp_diff = abs(row['vorp'] - target_player['vorp'])
            vorp_similarity = max(0, 1.0 - (vorp_diff / (target_player['vorp'] * 2)))
            
            # 风险相似度
            risk_diff = abs(row['total_risk'] - target_player['total_risk'])
            risk_similarity = max(0, 1.0 - risk_diff)
            
            # 综合相似度
            total_similarity = (
                position_similarity * 0.3 +
                age_similarity * 0.2 +
                vorp_similarity * 0.3 +
                risk_similarity * 0.2
            )
            
            return total_similarity
        
        # 计算所有球员的相似度
        evaluated_pool['similarity'] = evaluated_pool.apply(calculate_similarity, axis=1)
        
        # 排序并返回前 N 个
        similar_players = evaluated_pool[evaluated_pool['similarity'] > 0]
        similar_players = similar_players.sort_values('similarity', ascending=False).head(top_n)
        
        # 选择关键列
        similarity_columns = [
            'player_id', 'player_name', 'position', 'age',
            'vorp', 'adjusted_value', 'total_risk', 'similarity'
        ]
        
        return similar_players[[col for col in similarity_columns if col in similar_players.columns]]
