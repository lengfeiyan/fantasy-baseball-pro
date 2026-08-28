#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推荐系统
负责分析阵容需求并生成FA球员推荐
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger
logger = get_logger('recommendation')


class RecommendationSystem:
    """推荐系统"""
    
    def __init__(self, fa_analyzer):
        """
        初始化推荐系统
        
        Args:
            fa_analyzer: FA分析引擎实例
        """
        self.fa_analyzer = fa_analyzer
        self.logger = logger
        
        # 风险偏好配置
        self.risk_preferences = {
            'conservative': 0.8,
            'balanced': 1.0,
            'aggressive': 1.2
        }
        
        logger.info("初始化RecommendationSystem")
    
    def analyze_roster_needs(self, user_roster):
        """分析阵容需求"""
        try:
            if not user_roster:
                # 默认需求
                self.logger.info("使用默认阵容需求")
                return {
                    'C': 1.0,
                    '1B': 0.8,
                    '2B': 0.9,
                    '3B': 0.85,
                    'SS': 1.0,
                    'OF': 0.7,
                    'SP': 0.9,
                    'RP': 0.8
                }
            
            # 分析当前阵容
            roster_analysis = self._analyze_current_roster(user_roster)
            
            # 计算位置需求
            position_needs = self._calculate_position_needs(roster_analysis)
            
            self.logger.info(f"阵容需求分析完成: {position_needs}")
            return position_needs
        except Exception as e:
            self.logger.error(f"分析阵容需求失败: {str(e)}")
            # 返回默认需求
            return {
                'C': 1.0,
                '1B': 0.8,
                '2B': 0.9,
                '3B': 0.85,
                'SS': 1.0,
                'OF': 0.7,
                'SP': 0.9,
                'RP': 0.8
            }
    
    def _analyze_current_roster(self, user_roster):
        """分析当前阵容"""
        analysis = {
            'position_counts': {},
            'position_performance': {},
            'injured_players': 0
        }
        
        # 统计各位置球员数量和表现
        for player in user_roster:
            pos = player['pos']
            
            # 统计位置数量
            if pos not in analysis['position_counts']:
                analysis['position_counts'][pos] = 0
            analysis['position_counts'][pos] += 1
            
            # 统计位置表现（如果有表现数据）
            if 'performance' in player:
                if pos not in analysis['position_performance']:
                    analysis['position_performance'][pos] = []
                analysis['position_performance'][pos].append(player['performance'])
            
            # 统计伤病球员
            if player.get('status') == 'injured':
                analysis['injured_players'] += 1
        
        # 计算各位置平均表现
        for pos, performances in analysis['position_performance'].items():
            analysis['position_performance'][pos] = np.mean(performances) if performances else 0
        
        return analysis
    
    def _calculate_position_needs(self, roster_analysis):
        """计算位置需求"""
        # 标准阵容配置
        standard_config = {
            'C': 1,
            '1B': 1,
            '2B': 1,
            '3B': 1,
            'SS': 1,
            'OF': 3,
            'SP': 5,
            'RP': 3
        }
        
        needs = {}
        for pos, standard_count in standard_config.items():
            current_count = roster_analysis['position_counts'].get(pos, 0)
            performance = roster_analysis['position_performance'].get(pos, 0)
            
            # 计算需求分数
            # 基础需求：位置缺口
            base_need = max(0, (standard_count - current_count) / standard_count)
            
            # 表现需求：表现越差，需求越高
            performance_need = max(0, (100 - performance) / 100) if performance > 0 else 0.5
            
            # 综合需求
            needs[pos] = min(1.0, base_need * 0.7 + performance_need * 0.3)
        
        return needs
    
    def generate_recommendations(self, user_roster=None, position=None, top_n=10, risk_preference='balanced'):
        """生成推荐"""
        try:
            self.logger.info(f"生成FA推荐，位置: {position}, 数量: {top_n}, 风险偏好: {risk_preference}")
            
            # 1. 分析阵容需求
            roster_needs = self.analyze_roster_needs(user_roster)
            
            # 2. 获取FA球员池
            fa_pool = self.fa_analyzer.get_fa_pool(position)
            
            if not fa_pool:
                self.logger.warning("FA池为空")
                return []
            
            # 3. 计算每个FA球员的价值
            player_evaluations = []
            for player in fa_pool:
                try:
                    evaluation = self._evaluate_player(player, roster_needs, risk_preference)
                    if evaluation:
                        player_evaluations.append(evaluation)
                except Exception as e:
                    self.logger.warning(f"评估球员 {player['player_id']} 失败: {str(e)}")
                    continue
            
            # 4. 排序并生成推荐
            sorted_evaluations = self._sort_evaluations(player_evaluations)
            recommendations = sorted_evaluations[:top_n]
            
            self.logger.info(f"生成推荐完成，共 {len(recommendations)} 名球员")
            return recommendations
        except Exception as e:
            self.logger.error(f"生成推荐失败: {str(e)}")
            return []
    
    def _evaluate_player(self, player, roster_needs, risk_preference):
        """评估球员"""
        # 获取球员价值
        value = self.fa_analyzer.calculate_fa_value(player['player_id'])
        
        # 获取位置需求
        pos = player['pos']
        need_factor = roster_needs.get(pos, 0.5)
        
        # 风险调整
        risk_adjustment = self._calculate_risk_adjustment(player['player_id'], risk_preference)
        
        # 计算最终得分
        final_score = value['overall_value'] * (1 + need_factor * 0.5) * risk_adjustment
        
        # 构建评估结果
        evaluation = {
            'player_id': player['player_id'],
            'name': player['name'],
            'team': player['team'],
            'pos': pos,
            'value': value,
            'need_factor': need_factor,
            'risk_adjustment': risk_adjustment,
            'final_score': final_score
        }
        
        return evaluation
    
    def _calculate_risk_adjustment(self, player_id, risk_preference):
        """计算风险调整因子"""
        try:
            # 获取球员详情
            details = self.fa_analyzer.get_player_details(player_id)
            
            # 基础风险因子
            risk_factor = 1.0
            
            # 伤病风险
            if details.get('injury'):
                injury_severity = details['injury'].get('severity', 'mild')
                injury_factors = {
                    'mild': 0.95,
                    'moderate': 0.8,
                    'severe': 0.6,
                    'long_term': 0.3
                }
                risk_factor *= injury_factors.get(injury_severity, 0.95)
            
            # 风险偏好调整
            preference_factor = self.risk_preferences.get(risk_preference, 1.0)
            risk_adjustment = risk_factor * preference_factor
            
            return risk_adjustment
        except Exception as e:
            self.logger.warning(f"计算风险调整失败: {str(e)}")
            return 1.0
    
    def _sort_evaluations(self, evaluations):
        """排序评估结果"""
        # 按最终得分排序
        sorted_evaluations = sorted(evaluations, key=lambda x: x['final_score'], reverse=True)
        
        return sorted_evaluations
    
    def rank_fa_players(self, position=None, top_n=20):
        """排名FA球员"""
        try:
            self.logger.info(f"排名FA球员，位置: {position}, 数量: {top_n}")
            
            # 获取FA球员池
            fa_pool = self.fa_analyzer.get_fa_pool(position)
            
            if not fa_pool:
                self.logger.warning("FA池为空")
                return []
            
            # 计算每个球员的价值
            player_values = []
            for player in fa_pool:
                try:
                    value = self.fa_analyzer.calculate_fa_value(player['player_id'])
                    player_values.append(value)
                except Exception as e:
                    self.logger.warning(f"计算球员 {player['player_id']} 价值失败: {str(e)}")
                    continue
            
            # 按价值排序
            sorted_players = sorted(player_values, key=lambda x: x['overall_value'], reverse=True)
            ranked_players = sorted_players[:top_n]
            
            # 添加排名
            for i, player in enumerate(ranked_players, 1):
                player['rank'] = i
            
            self.logger.info(f"排名完成，共 {len(ranked_players)} 名球员")
            return ranked_players
        except Exception as e:
            self.logger.error(f"排名FA球员失败: {str(e)}")
            return []
    
    def get_position_recommendations(self, position, top_n=10):
        """获取特定位置的推荐"""
        return self.generate_recommendations(position=position, top_n=top_n)
    
    def analyze_waiver_wire_priority(self, user_roster, waiver_wire_players):
        """分析Waiver Wire优先级"""
        try:
            self.logger.info("分析Waiver Wire优先级")
            
            # 分析阵容需求
            roster_needs = self.analyze_roster_needs(user_roster)
            
            # 评估每个Waiver Wire球员
            evaluations = []
            for player in waiver_wire_players:
                try:
                    evaluation = self._evaluate_player(player, roster_needs, 'balanced')
                    if evaluation:
                        evaluations.append(evaluation)
                except Exception as e:
                    self.logger.warning(f"评估Waiver Wire球员 {player['player_id']} 失败: {str(e)}")
                    continue
            
            # 排序并返回
            sorted_evaluations = self._sort_evaluations(evaluations)
            
            self.logger.info(f"Waiver Wire优先级分析完成，共 {len(sorted_evaluations)} 名球员")
            return sorted_evaluations
        except Exception as e:
            self.logger.error(f"分析Waiver Wire优先级失败: {str(e)}")
            return []
    
    def export_recommendations(self, recommendations, output_file):
        """导出推荐结果"""
        try:
            self.logger.info(f"导出推荐结果到: {output_file}")
            
            # 转换为DataFrame
            data = []
            for rec in recommendations:
                data.append({
                    'rank': rec.get('rank', ''),
                    'name': rec['name'],
                    'team': rec['team'],
                    'pos': rec['pos'],
                    'overall_value': rec['value']['overall_value'],
                    'base_score': rec['value']['base_score'],
                    'statcast_score': rec['value']['statcast_score'],
                    'need_factor': rec['need_factor'],
                    'risk_adjustment': rec['risk_adjustment'],
                    'final_score': rec['final_score']
                })
            
            df = pd.DataFrame(data)
            
            # 导出到CSV
            df.to_csv(output_file, index=False)
            
            self.logger.info(f"推荐结果导出成功: {output_file}")
            return True
        except Exception as e:
            self.logger.error(f"导出推荐结果失败: {str(e)}")
            return False
