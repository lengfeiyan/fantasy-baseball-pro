#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Statcast 数据模块
负责获取、处理和存储 Statcast 高级数据
"""

import os
import time
import requests
import pandas as pd
from typing import Dict, Any, Optional, List


class StatcastFetcher:
    """Statcast 数据获取器"""
    
    def __init__(self, cache_dir: str = 'data/cache'):
        """
        初始化 Statcast 数据获取器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.base_url = 'https://baseballsavant.mlb.com/statcast_search/csv'
        self.cache_expiry = 24 * 3600  # 24小时
    
    def fetch_hitter_data(self, player_id: str) -> Optional[pd.DataFrame]:
        """
        获取打者 Statcast 数据
        
        Args:
            player_id: 球员 ID
            
        Returns:
            Optional[pd.DataFrame]: 打者 Statcast 数据
        """
        cache_file = os.path.join(self.cache_dir, f'statcast_hitter_{player_id}.csv')
        
        # 检查缓存
        if os.path.exists(cache_file):
            file_mod_time = os.path.getmtime(cache_file)
            if time.time() - file_mod_time < self.cache_expiry:
                return pd.read_csv(cache_file)
        
        # 获取数据
        try:
            params = {
                'player_type': 'batter',
                'player_id': player_id,
                'type': 'details'
            }
            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 200:
                # 保存到缓存
                with open(cache_file, 'w') as f:
                    f.write(response.text)
                
                # 读取并返回数据
                df = pd.read_csv(cache_file)
                return self._process_hitter_data(df)
            else:
                print(f"❌ 获取打者 Statcast 数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 获取打者 Statcast 数据失败: {e}")
            return None
    
    def fetch_pitcher_data(self, player_id: str) -> Optional[pd.DataFrame]:
        """
        获取投手 Statcast 数据
        
        Args:
            player_id: 球员 ID
            
        Returns:
            Optional[pd.DataFrame]: 投手 Statcast 数据
        """
        cache_file = os.path.join(self.cache_dir, f'statcast_pitcher_{player_id}.csv')
        
        # 检查缓存
        if os.path.exists(cache_file):
            file_mod_time = os.path.getmtime(cache_file)
            if time.time() - file_mod_time < self.cache_expiry:
                return pd.read_csv(cache_file)
        
        # 获取数据
        try:
            params = {
                'player_type': 'pitcher',
                'player_id': player_id,
                'type': 'details'
            }
            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 200:
                # 保存到缓存
                with open(cache_file, 'w') as f:
                    f.write(response.text)
                
                # 读取并返回数据
                df = pd.read_csv(cache_file)
                return self._process_pitcher_data(df)
            else:
                print(f"❌ 获取投手 Statcast 数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 获取投手 Statcast 数据失败: {e}")
            return None
    
    def _process_hitter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理打者 Statcast 数据
        
        Args:
            df: 原始打者 Statcast 数据
            
        Returns:
            pd.DataFrame: 处理后的打者 Statcast 数据
        """
        # 选择关键列
        key_columns = [
            'player_name', 'game_date', 'events', 'description',
            'launch_speed', 'launch_angle', 'estimated_woba_using_speedangle',
            'barrel', 'hard_hit', 'iso_value', 'woba_value'
        ]
        
        # 过滤列
        df = df[[col for col in key_columns if col in df.columns]]
        
        # 计算高级指标
        if not df.empty:
            # 计算平均 exit velocity
            df['avg_exit_velocity'] = df['launch_speed'].mean()
            
            # 计算平均 launch angle
            df['avg_launch_angle'] = df['launch_angle'].mean()
            
            # 计算 barrel rate
            if 'barrel' in df.columns:
                df['barrel_rate'] = (df['barrel'] == 'true').mean()
            
            # 计算 hard hit rate
            if 'hard_hit' in df.columns:
                df['hard_hit_rate'] = (df['hard_hit'] == 'true').mean()
            
            # 计算 xwOBA
            if 'estimated_woba_using_speedangle' in df.columns:
                df['xwoba'] = df['estimated_woba_using_speedangle'].mean()
        
        return df
    
    def _process_pitcher_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理投手 Statcast 数据
        
        Args:
            df: 原始投手 Statcast 数据
            
        Returns:
            pd.DataFrame: 处理后的投手 Statcast 数据
        """
        # 选择关键列
        key_columns = [
            'player_name', 'game_date', 'events', 'description',
            'launch_speed', 'launch_angle', 'estimated_woba_using_speedangle',
            'strikeout_probability', 'walk_probability', 'xba', 'xwoba'
        ]
        
        # 过滤列
        df = df[[col for col in key_columns if col in df.columns]]
        
        # 计算高级指标
        if not df.empty:
            # 计算平均 exit velocity against
            df['exit_velocity_against'] = df['launch_speed'].mean()
            
            # 计算平均 xwOBA against
            if 'xwoba' in df.columns:
                df['xwoba_against'] = df['xwoba'].mean()
            elif 'estimated_woba_using_speedangle' in df.columns:
                df['xwoba_against'] = df['estimated_woba_using_speedangle'].mean()
            
            # 计算 strikeout probability
            if 'strikeout_probability' in df.columns:
                df['avg_strikeout_prob'] = df['strikeout_probability'].mean()
            
            # 计算 walk probability
            if 'walk_probability' in df.columns:
                df['avg_walk_prob'] = df['walk_probability'].mean()
        
        return df
    
    def integrate_with_player_pool(self, player_pool: pd.DataFrame) -> pd.DataFrame:
        """
        将 Statcast 数据融合到球员池
        
        Args:
            player_pool: 球员池数据
            
        Returns:
            pd.DataFrame: 融合了 Statcast 数据的球员池
        """
        # 复制球员池
        enhanced_pool = player_pool.copy()
        
        # 添加 Statcast 列
        statcast_columns = [
            'xwoba', 'avg_exit_velocity', 'avg_launch_angle',
            'barrel_rate', 'hard_hit_rate', 'exit_velocity_against',
            'xwoba_against', 'avg_strikeout_prob', 'avg_walk_prob'
        ]
        
        for col in statcast_columns:
            if col not in enhanced_pool.columns:
                enhanced_pool[col] = None
        
        # 遍历球员，获取 Statcast 数据
        for idx, row in enhanced_pool.iterrows():
            player_id = row.get('player_id')
            position = row.get('position')
            
            if player_id:
                if position in ['C', '1B', '2B', '3B', 'SS', 'OF']:
                    # 打者
                    statcast_data = self.fetch_hitter_data(str(player_id))
                    if statcast_data is not None and not statcast_data.empty:
                        # 更新 Statcast 数据
                        if 'xwoba' in statcast_data.columns:
                            enhanced_pool.at[idx, 'xwoba'] = statcast_data['xwoba'].iloc[0]
                        if 'avg_exit_velocity' in statcast_data.columns:
                            enhanced_pool.at[idx, 'avg_exit_velocity'] = statcast_data['avg_exit_velocity'].iloc[0]
                        if 'avg_launch_angle' in statcast_data.columns:
                            enhanced_pool.at[idx, 'avg_launch_angle'] = statcast_data['avg_launch_angle'].iloc[0]
                        if 'barrel_rate' in statcast_data.columns:
                            enhanced_pool.at[idx, 'barrel_rate'] = statcast_data['barrel_rate'].iloc[0]
                        if 'hard_hit_rate' in statcast_data.columns:
                            enhanced_pool.at[idx, 'hard_hit_rate'] = statcast_data['hard_hit_rate'].iloc[0]
                elif position in ['SP', 'RP']:
                    # 投手
                    statcast_data = self.fetch_pitcher_data(str(player_id))
                    if statcast_data is not None and not statcast_data.empty:
                        # 更新 Statcast 数据
                        if 'exit_velocity_against' in statcast_data.columns:
                            enhanced_pool.at[idx, 'exit_velocity_against'] = statcast_data['exit_velocity_against'].iloc[0]
                        if 'xwoba_against' in statcast_data.columns:
                            enhanced_pool.at[idx, 'xwoba_against'] = statcast_data['xwoba_against'].iloc[0]
                        if 'avg_strikeout_prob' in statcast_data.columns:
                            enhanced_pool.at[idx, 'avg_strikeout_prob'] = statcast_data['avg_strikeout_prob'].iloc[0]
                        if 'avg_walk_prob' in statcast_data.columns:
                            enhanced_pool.at[idx, 'avg_walk_prob'] = statcast_data['avg_walk_prob'].iloc[0]
        
        return enhanced_pool
