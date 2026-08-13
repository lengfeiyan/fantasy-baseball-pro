#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FA分析引擎核心逻辑
负责计算FA球员价值和生成推荐
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
from config_loader import get_config
logger = get_logger('fa_analyzer')


class FAAnalyzer:
    """FA球员分析引擎"""
    
    def __init__(self, db_path='fantasy_baseball.db'):
        """
        初始化FA分析引擎
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.config = get_config()
        self.scoring_rules = self.config['league']['scoring']
        self.fa_config = self.config.get('fa_analyzer', {})
        self.conn = None
        self.cursor = None
        
        # 位置稀缺性指数
        self.position_scarcity = {
            'C': 1.3,
            'SS': 1.2,
            '2B': 1.1,
            '3B': 1.05,
            '1B': 0.9,
            'OF': 0.85,
            'SP': 1.0,
            'RP': 1.15
        }
        
        # 伤病影响因子
        self.injury_factors = {
            'mild': 0.85,
            'moderate': 0.65,
            'severe': 0.4,
            'long_term': 0.15
        }
        
        logger.info(f"初始化FAAnalyzer，数据库路径: {db_path}")
    
    def connect_db(self):
        """连接到数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            raise
    
    def disconnect_db(self):
        """断开数据库连接"""
        if self.conn:
            self.conn.close()
    
    def get_fa_pool(self, position=None):
        """获取FA球员池"""
        try:
            self.connect_db()
            
            query = "SELECT * FROM fa_pool WHERE status = 'available'"
            params = []
            
            if position:
                query += " AND pos = ?"
                params.append(position)
            
            self.cursor.execute(query, params)
            fa_players = self.cursor.fetchall()
            
            # 转换为字典列表
            result = []
            for player in fa_players:
                result.append({
                    'id': player[0],
                    'player_id': player[1],
                    'name': player[2],
                    'team': player[3],
                    'pos': player[4],
                    'status': player[5],
                    'last_updated': player[6]
                })
            
            logger.info(f"获取FA池数据，共 {len(result)} 名球员")
            return result
        except Exception as e:
            logger.error(f"获取FA池失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
    
    def calculate_fa_value(self, player_id):
        """计算FA球员价值"""
        try:
            # 1. 获取球员实时统计数据
            from .real_time_data import RealTimeData
            rtd = RealTimeData(self.db_path)
            player_stats = rtd.fetch_player_stats(player_id)
            
            # 2. 应用评分规则计算基础分数
            base_score = self._calculate_base_score(player_stats)
            
            # 3. 考虑最近表现趋势调整分数
            trend_score = self._calculate_trend_score(player_stats)
            
            # 4. 根据伤病情况调整预期价值
            injury_adjusted_value = self._adjust_for_injury(player_id, base_score)
            
            # 5. 考虑位置稀缺性调整价值
            position_adjusted_value = self._adjust_for_position_scarcity(player_stats['pos'], injury_adjusted_value)
            
            # 6. 整合Statcast数据
            statcast_score = self._calculate_statcast_score(player_stats)
            
            # 7. 计算综合价值评分
            overall_value = self._calculate_overall_value(
                position_adjusted_value, trend_score, statcast_score
            )
            
            logger.info(f"计算球员 {player_id} 的价值: {overall_value}")
            return {
                'player_id': player_id,
                'name': player_stats['name'],
                'pos': player_stats['pos'],
                'base_score': base_score,
                'trend_score': trend_score,
                'injury_adjusted_value': injury_adjusted_value,
                'position_adjusted_value': position_adjusted_value,
                'statcast_score': statcast_score,
                'overall_value': overall_value
            }
        except Exception as e:
            logger.error(f"计算球员价值失败: {str(e)}")
            raise
    
    def _calculate_base_score(self, player_stats):
        """计算基础分数"""
        score = 0
        pos = player_stats['pos']
        stats = player_stats.get('stats', {})
        
        # 根据位置应用不同的评分规则
        if pos in ['C', '1B', '2B', '3B', 'SS', 'OF']:
            # 打者评分
            for stat, weight in self.scoring_rules.get('hitters', {}).items():
                if stat in stats:
                    score += stats[stat] * weight
        elif pos in ['SP', 'RP']:
            # 投手评分
            for stat, weight in self.scoring_rules.get('pitchers', {}).items():
                if stat in stats:
                    score += stats[stat] * weight
        
        return score
    
    def _calculate_trend_score(self, player_stats):
        """计算趋势分数"""
        # 模拟趋势分数计算
        # 实际项目中需要根据最近比赛数据计算
        return np.random.normal(100, 10)  # 模拟趋势分数
    
    def _adjust_for_injury(self, player_id, base_score):
        """根据伤病情况调整价值"""
        try:
            self.connect_db()
            
            # 查询球员的伤病情况
            self.cursor.execute('''
            SELECT severity FROM injury_reports 
            WHERE player_id = ? AND status != 'recovered' 
            ORDER BY start_date DESC LIMIT 1
            ''', (player_id,))
            injury = self.cursor.fetchone()
            
            if injury:
                severity = injury[0]
                factor = self.injury_factors.get(severity, 1.0)
                adjusted_value = base_score * factor
                logger.info(f"球员 {player_id} 因伤病调整价值: {adjusted_value}")
                return adjusted_value
            
            return base_score
        except Exception as e:
            logger.error(f"伤病调整失败: {str(e)}")
            return base_score
        finally:
            self.disconnect_db()
    
    def _adjust_for_position_scarcity(self, position, value):
        """根据位置稀缺性调整价值"""
        factor = self.position_scarcity.get(position, 1.0)
        adjusted_value = value * factor
        logger.info(f"位置 {position} 稀缺性调整后价值: {adjusted_value}")
        return adjusted_value
    
    def _calculate_statcast_score(self, player_stats):
        """计算Statcast评分"""
        statcast_data = player_stats.get('statcast', {})
        if not statcast_data:
            return 0
        
        pos = player_stats['pos']
        score = 0
        
        if pos in ['C', '1B', '2B', '3B', 'SS', 'OF']:
            # 打者Statcast评分
            score = (
                (statcast_data.get('xwOBA', 0) * 300) +  # xwOBA标准化
                (statcast_data.get('barrel_rate', 0) * 100) +
                (statcast_data.get('exit_velocity', 0) * 1) +
                (statcast_data.get('hard_hit_rate', 0) * 100) +
                (statcast_data.get('swing_contact_rate', 0) * 100)
            )
        elif pos in ['SP', 'RP']:
            # 投手Statcast评分
            score = (
                ((3 - statcast_data.get('xERA', 5)) * 20) +  # xERA越低越好
                (statcast_data.get('whiff_rate', 0) * 100) +
                (statcast_data.get('spin_rate', 0) * 0.1) +
                (statcast_data.get('velocity', 0) * 2) +
                ((1 - statcast_data.get('hard_hit_allowed_rate', 1)) * 100)
            )
        
        # 标准化到0-100分
        score = min(max(score, 0), 100)
        return score
    
    def _calculate_overall_value(self, position_adjusted_value, trend_score, statcast_score):
        """计算综合价值"""
        # 权重配置
        weights = {
            'position_adjusted': 0.3,
            'trend': 0.15,
            'statcast': 0.25,
            'vorp': 0.3  # 预留VORP权重
        }
        
        # 计算综合评分
        overall = (
            position_adjusted_value * weights['position_adjusted'] +
            trend_score * weights['trend'] +
            statcast_score * weights['statcast'] +
            position_adjusted_value * weights['vorp']  # 暂时使用位置调整后的值代替VORP
        )
        
        return overall
    
    def calculate_vorp(self, player_id):
        """计算球员VORP"""
        try:
            self.connect_db()
            
            # 获取球员数据
            from .real_time_data import RealTimeData
            rtd = RealTimeData(self.db_path)
            player_stats = rtd.fetch_player_stats(player_id)
            
            pos = player_stats['pos']
            base_score = self._calculate_base_score(player_stats)
            
            # 计算替代球员水平
            replacement_level = self._calculate_replacement_level(pos)
            
            # 计算VORP
            vorp = (base_score - replacement_level) * self._get_playing_time_factor(player_id)
            
            logger.info(f"球员 {player_id} 的VORP: {vorp}")
            return vorp
        except Exception as e:
            logger.error(f"计算VORP失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
    
    def _calculate_replacement_level(self, position):
        """计算替代球员水平"""
        # 模拟替代球员水平计算
        # 实际项目中需要根据联盟数据计算
        replacement_levels = {
            'C': 50,
            '1B': 60,
            '2B': 55,
            '3B': 58,
            'SS': 52,
            'OF': 56,
            'SP': 45,
            'RP': 40
        }
        return replacement_levels.get(position, 50)
    
    def _get_playing_time_factor(self, player_id):
        """获取上场时间调整因子"""
        # 模拟上场时间调整
        return np.random.uniform(0.8, 1.0)
    
    def get_recommendations(self, user_roster=None, top_n=10):
        """获取FA推荐"""
        try:
            # 1. 分析用户阵容需求
            roster_needs = self._analyze_roster_needs(user_roster)
            
            # 2. 获取FA球员池
            fa_pool = self.get_fa_pool()
            
            # 3. 计算每个FA球员的价值
            player_values = []
            for player in fa_pool:
                try:
                    value = self.calculate_fa_value(player['player_id'])
                    player_values.append(value)
                except Exception as e:
                    logger.warning(f"计算球员 {player['player_id']} 价值失败: {str(e)}")
                    continue
            
            # 4. 根据位置需求和价值排序
            sorted_players = self._rank_players_by_need(player_values, roster_needs)
            
            # 5. 生成推荐列表
            recommendations = sorted_players[:top_n]
            
            logger.info(f"生成FA推荐，共 {len(recommendations)} 名球员")
            return recommendations
        except Exception as e:
            logger.error(f"获取推荐失败: {str(e)}")
            raise
    
    def _analyze_roster_needs(self, user_roster):
        """分析阵容需求"""
        # 模拟阵容需求分析
        # 实际项目中需要根据用户阵容计算
        if not user_roster:
            # 默认需求
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
        
        # 简单的需求计算
        needs = {}
        for pos in ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP']:
            # 计算该位置的球员数量
            pos_players = [p for p in user_roster if p['pos'] == pos]
            # 简单需求计算：位置越缺，需求越高
            needs[pos] = max(0, 1.0 - len(pos_players) * 0.2)
        
        return needs
    
    def _rank_players_by_need(self, player_values, roster_needs):
        """根据需求对球员排序"""
        # 计算每个球员的综合得分（价值 + 需求权重）
        for player in player_values:
            pos = player['pos']
            need_factor = roster_needs.get(pos, 0.5)
            player['final_score'] = player['overall_value'] * (1 + need_factor * 0.5)
        
        # 按最终得分排序
        sorted_players = sorted(player_values, key=lambda x: x['final_score'], reverse=True)
        
        return sorted_players
    
    def get_player_details(self, player_id):
        """获取球员详细信息"""
        try:
            from .real_time_data import RealTimeData
            rtd = RealTimeData(self.db_path)
            player_stats = rtd.fetch_player_stats(player_id)
            
            # 获取伤病信息
            self.connect_db()
            self.cursor.execute('''
            SELECT * FROM injury_reports 
            WHERE player_id = ? 
            ORDER BY start_date DESC LIMIT 1
            ''', (player_id,))
            injury = self.cursor.fetchone()
            
            injury_info = None
            if injury:
                injury_info = {
                    'type': injury[3],
                    'severity': injury[4],
                    'start_date': injury[5],
                    'expected_return': injury[6],
                    'status': injury[7]
                }
            
            # 获取价值评估
            value = self.calculate_fa_value(player_id)
            
            return {
                'player_id': player_id,
                'name': player_stats['name'],
                'team': player_stats['team'],
                'pos': player_stats['pos'],
                'stats': player_stats.get('stats', {}),
                'statcast': player_stats.get('statcast', {}),
                'injury': injury_info,
                'value': value
            }
        except Exception as e:
            logger.error(f"获取球员详情失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
