#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
伤病数据模块
负责获取、处理和存储伤病数据
"""

import os
import time
import requests
import pandas as pd
from typing import Dict, Any, Optional, List


class InjuryDataFetcher:
    """伤病数据获取器"""
    
    def __init__(self, cache_dir: str = 'data/cache'):
        """
        初始化伤病数据获取器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.base_url = 'https://statsapi.mlb.com/api/v1'
        self.cache_expiry = 12 * 3600  # 12小时
    
    def fetch_injury_data(self, player_id: str) -> Optional[pd.DataFrame]:
        """
        获取球员伤病数据
        
        Args:
            player_id: 球员 ID
            
        Returns:
            Optional[pd.DataFrame]: 球员伤病数据
        """
        cache_file = os.path.join(self.cache_dir, f'injury_{player_id}.csv')
        
        # 检查缓存
        if os.path.exists(cache_file):
            file_mod_time = os.path.getmtime(cache_file)
            if time.time() - file_mod_time < self.cache_expiry:
                return pd.read_csv(cache_file)
        
        # 获取数据
        try:
            # 构建 API URL
            url = f"{self.base_url}/people/{player_id}/stats/game/{player_id}"
            params = {
                'stats': 'season',
                'season': '2026'
            }
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # 处理数据
                injury_data = self._process_injury_data(data)
                
                # 保存到缓存
                if injury_data is not None:
                    injury_data.to_csv(cache_file, index=False)
                
                return injury_data
            else:
                print(f"❌ 获取伤病数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 获取伤病数据失败: {e}")
            return None
    
    def _process_injury_data(self, data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        处理伤病数据
        
        Args:
            data: 原始伤病数据
            
        Returns:
            Optional[pd.DataFrame]: 处理后的伤病数据
        """
        # 这里是模拟实现，实际实现需要根据 API 返回格式调整
        # 构建模拟伤病数据
        injury_records = [
            {
                'injury_date': '2025-05-15',
                'injury_type': 'hamstring strain',
                'severity': 'medium',
                'days_missed': 15,
                'recovery_status': 'fully recovered'
            },
            {
                'injury_date': '2024-09-20',
                'injury_type': 'shoulder inflammation',
                'severity': 'mild',
                'days_missed': 7,
                'recovery_status': 'fully recovered'
            }
        ]
        
        return pd.DataFrame(injury_records)
    
    def get_injury_history(self, player_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取球员伤病历史
        
        Args:
            player_id: 球员 ID
            
        Returns:
            Optional[List[Dict[str, Any]]]: 球员伤病历史
        """
        injury_data = self.fetch_injury_data(player_id)
        if injury_data is not None and not injury_data.empty:
            return injury_data.to_dict('records')
        return []


class InjuryRiskModel:
    """伤病风险评估模型"""
    
    def __init__(self, injury_fetcher: Optional[InjuryDataFetcher] = None):
        """
        初始化伤病风险评估模型
        
        Args:
            injury_fetcher: 伤病数据获取器
        """
        self.injury_fetcher = injury_fetcher or InjuryDataFetcher()
        
        # 位置风险系数
        self.position_risk_factors = {
            'C': 1.8,    # 捕手风险最高
            'SP': 1.6,   # 先发投手风险高
            'RP': 1.4,   # 中继投手风险较高
            'OF': 1.2,   # 外野手风险中等
            '2B': 1.2,   # 二垒手风险中等
            'SS': 1.2,   # 游击手风险中等
            '3B': 1.1,   # 三垒手风险较低
            '1B': 1.0,   # 一垒手风险最低
            'UTIL': 1.0  # 工具人风险最低
        }
        
        # 年龄风险系数
        self.age_risk_factors = {
            (20, 25): 0.8,    # 年轻球员风险较低
            (26, 30): 1.0,    # 巅峰期球员风险中等
            (31, 35): 1.3,    # 老将风险较高
            (36, 40): 1.6,    # 大龄球员风险很高
            (41, 100): 2.0    # 超龄球员风险极高
        }
    
    def calculate_risk_score(self, player_id: str, position: str, age: int, innings_pitched: Optional[float] = None, plate_appearances: Optional[int] = None) -> float:
        """
        计算球员伤病风险评分
        
        Args:
            player_id: 球员 ID
            position: 球员位置
            age: 球员年龄
            innings_pitched: 投手 innings pitched
            plate_appearances: 打者 plate appearances
            
        Returns:
            float: 伤病风险评分 (0-1)
        """
        risk_score = 0.0
        
        # 位置风险
        position_risk = self.position_risk_factors.get(position, 1.0)
        risk_score += position_risk * 0.3
        
        # 年龄风险
        age_risk = 1.0
        for age_range, factor in self.age_risk_factors.items():
            if age_range[0] <= age <= age_range[1]:
                age_risk = factor
                break
        risk_score += age_risk * 0.2
        
        # 负荷风险
        load_risk = 1.0
        if position in ['SP', 'RP'] and innings_pitched:
            if innings_pitched > 200:
                load_risk = 1.5
            elif innings_pitched > 180:
                load_risk = 1.3
            elif innings_pitched > 150:
                load_risk = 1.1
        elif position not in ['SP', 'RP'] and plate_appearances:
            if plate_appearances > 700:
                load_risk = 1.3
            elif plate_appearances > 600:
                load_risk = 1.1
        risk_score += load_risk * 0.2
        
        # 历史风险
        history_risk = 1.0
        injury_history = self.injury_fetcher.get_injury_history(player_id)
        if injury_history:
            # 计算过去两年的伤病次数
            recent_injuries = [inj for inj in injury_history if '2024' in inj.get('injury_date', '') or '2025' in inj.get('injury_date', '')]
            if len(recent_injuries) >= 3:
                history_risk = 1.8
            elif len(recent_injuries) == 2:
                history_risk = 1.4
            elif len(recent_injuries) == 1:
                history_risk = 1.1
        risk_score += history_risk * 0.3
        
        # 归一化到 0-1 范围
        normalized_score = min(1.0, risk_score / 3.0)
        
        return normalized_score
    
    def get_risk_factors(self, player_id: str, position: str, age: int) -> Dict[str, float]:
        """
        获取球员的关键风险因素
        
        Args:
            player_id: 球员 ID
            position: 球员位置
            age: 球员年龄
            
        Returns:
            Dict[str, float]: 风险因素
        """
        # 位置风险
        position_risk = self.position_risk_factors.get(position, 1.0)
        
        # 年龄风险
        age_risk = 1.0
        for age_range, factor in self.age_risk_factors.items():
            if age_range[0] <= age <= age_range[1]:
                age_risk = factor
                break
        
        # 历史风险
        history_risk = 1.0
        injury_history = self.injury_fetcher.get_injury_history(player_id)
        if injury_history:
            recent_injuries = [inj for inj in injury_history if '2024' in inj.get('injury_date', '') or '2025' in inj.get('injury_date', '')]
            if len(recent_injuries) >= 3:
                history_risk = 1.8
            elif len(recent_injuries) == 2:
                history_risk = 1.4
            elif len(recent_injuries) == 1:
                history_risk = 1.1
        
        return {
            'position_risk': position_risk,
            'age_risk': age_risk,
            'history_risk': history_risk
        }
    
    def adjust_player_value(self, player_value: float, risk_score: float) -> float:
        """
        根据伤病风险调整球员价值
        
        Args:
            player_value: 原始球员价值
            risk_score: 伤病风险评分
            
        Returns:
            float: 调整后的球员价值
        """
        # 风险调整因子
        risk_adjustment = 1.0 - (risk_score * 0.3)  # 最高降低 30% 的价值
        
        return player_value * risk_adjustment
    
    def integrate_with_player_pool(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        将伤病风险评分融合到球员池
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 融合了伤病风险评分的球员池
        """
        # 复制球员池
        risk_pool = player_pool.copy()
        
        # 添加伤病风险列
        if 'injury_risk_score' not in risk_pool.columns:
            risk_pool['injury_risk_score'] = None
        
        if 'adjusted_value' not in risk_pool.columns:
            risk_pool['adjusted_value'] = None
        
        # 遍历球员，计算伤病风险评分
        for idx, row in risk_pool.iterrows():
            player_id = row.get('player_id', '')
            position = row.get('position', '')
            age = row.get('age', 25)
            player_value = row.get('vorp', 0)
            
            # 计算风险评分
            risk_score = self.calculate_risk_score(player_id, position, age)
            
            # 调整球员价值
            adjusted_value = self.adjust_player_value(player_value, risk_score)
            
            # 更新球员池
            risk_pool.at[idx, 'injury_risk_score'] = risk_score
            risk_pool.at[idx, 'adjusted_value'] = adjusted_value
        
        return risk_pool
