#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险分析器模块
负责分析球员的风险因素，包括伤病风险和表现稳定性
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from data.injury_data import InjuryRiskModel


class RiskAnalyzer:
    """风险分析器"""
    
    def __init__(self, injury_risk_model: Optional[InjuryRiskModel] = None):
        """
        初始化风险分析器
        
        Args:
            injury_risk_model: 伤病风险评估模型
        """
        self.injury_risk_model = injury_risk_model or InjuryRiskModel()
    
    def analyze_player_risk(self, player_data: pd.DataFrame) -> Dict[str, float]:
        """
        分析球员的风险
        
        Args:
            player_data: 球员数据
            
        Returns:
            Dict[str, float]: 风险分析结果
        """
        # 获取球员基本信息
        player_id = player_data.get('player_id', '')
        position = player_data.get('position', '')
        age = player_data.get('age', 25)
        
        # 计算伤病风险
        injury_risk = self.injury_risk_model.calculate_risk_score(player_id, position, age)
        
        # 计算表现稳定性风险
        performance_risk = self._calculate_performance_risk(player_data, position)
        
        # 计算总体风险
        total_risk = (injury_risk * 0.6) + (performance_risk * 0.4)  # 伤病风险权重更高
        
        # 计算风险调整后的价值
        original_value = player_data.get('vorp', 0)
        adjusted_value = self.injury_risk_model.adjust_player_value(original_value, total_risk)
        
        return {
            'injury_risk': injury_risk,
            'performance_risk': performance_risk,
            'total_risk': total_risk,
            'adjusted_value': adjusted_value
        }
    
    def _calculate_performance_risk(self, player_data: pd.DataFrame, position: str) -> float:
        """
        计算球员表现稳定性风险
        
        Args:
            player_data: 球员数据
            position: 球员位置
            
        Returns:
            float: 表现稳定性风险评分 (0-1)
        """
        # 这里是模拟实现，实际实现需要历史数据
        # 构建模拟的表现稳定性指标
        
        # 基础表现稳定性
        base_stability = 0.5
        
        # 整合 Statcast 数据评估稳定性
        statcast_stability = self._assess_statcast_stability(player_data, position)
        
        # 计算最终表现稳定性风险
        # 稳定性越高，风险越低
        performance_stability = (base_stability + statcast_stability) / 2
        performance_risk = 1.0 - performance_stability
        
        return performance_risk
    
    def _assess_statcast_stability(self, player_data: pd.DataFrame, position: str) -> float:
        """
        使用 Statcast 数据评估球员表现稳定性
        
        Args:
            player_data: 球员数据
            position: 球员位置
            
        Returns:
            float: 稳定性评分 (0-1)
        """
        stability = 0.5
        
        if position in ['C', '1B', '2B', '3B', 'SS', 'OF']:
            # 打者稳定性评估
            # exit velocity 一致性
            if 'avg_exit_velocity' in player_data:
                ev = player_data['avg_exit_velocity']
                if ev > 90:
                    stability += 0.2  # 高 exit velocity 通常更稳定
                elif ev < 80:
                    stability -= 0.2  # 低 exit velocity 通常不稳定
            
            # launch angle 一致性
            if 'avg_launch_angle' in player_data:
                la = player_data['avg_launch_angle']
                if 10 <= la <= 25:
                    stability += 0.1  # 理想 launch angle 范围
                elif la < 0 or la > 40:
                    stability -= 0.1  # 极端 launch angle 不稳定
        
        elif position in ['SP', 'RP']:
            # 投手稳定性评估
            # strikeout probability
            if 'avg_strikeout_prob' in player_data:
                k_prob = player_data['avg_strikeout_prob']
                if k_prob > 0.25:
                    stability += 0.2  # 高三振率通常更稳定
                elif k_prob < 0.15:
                    stability -= 0.2  # 低三振率通常不稳定
            
            # walk probability
            if 'avg_walk_prob' in player_data:
                bb_prob = player_data['avg_walk_prob']
                if bb_prob < 0.10:
                    stability += 0.1  # 低保送率通常更稳定
                elif bb_prob > 0.15:
                    stability -= 0.1  # 高保送率通常不稳定
        
        return max(0, min(1, stability))  # 确保稳定性在 0-1 范围内
    
    def analyze_all_players(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        分析球员池中的所有球员
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 包含风险分析的球员池
        """
        # 复制球员池
        risk_analyzed_pool = player_pool.copy()
        
        # 添加风险分析列
        risk_columns = [
            'injury_risk', 'performance_risk', 'total_risk', 'adjusted_value'
        ]
        
        for col in risk_columns:
            if col not in risk_analyzed_pool.columns:
                risk_analyzed_pool[col] = None
        
        # 遍历球员，分析风险
        for idx, player in risk_analyzed_pool.iterrows():
            risk_result = self.analyze_player_risk(player)
            
            # 更新球员池
            for key, value in risk_result.items():
                risk_analyzed_pool.at[idx, key] = value
        
        return risk_analyzed_pool
    
    def generate_risk_report(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        生成风险报告
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 风险报告
        """
        # 分析所有球员
        analyzed_pool = self.analyze_all_players(player_pool)
        
        # 选择关键列
        report_columns = [
            'player_id', 'player_name', 'position', 'age',
            'vorp', 'adjusted_value', 'injury_risk',
            'performance_risk', 'total_risk'
        ]
        
        # 过滤列
        report = analyzed_pool[[col for col in report_columns if col in analyzed_pool.columns]]
        
        # 按总风险排序
        report = report.sort_values('total_risk', ascending=False)
        
        return report
