#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时数据处理模块
负责获取实时球员数据、更新FA池和伤病数据
"""

import os
import json
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger
logger = get_logger('real_time_data')


class RealTimeData:
    """实时数据处理类"""
    
    def __init__(self, db_path='fantasy_baseball.db', cache_dir='data/cache'):
        """
        初始化实时数据处理类
        
        Args:
            db_path: 数据库文件路径
            cache_dir: 缓存目录
        """
        self.db_path = db_path
        self.cache_dir = cache_dir
        self.conn = None
        self.cursor = None
        
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 缓存过期时间（秒）
        self.cache_expiry = 24 * 3600  # 24小时
        
        logger.info(f"初始化RealTimeData，数据库路径: {db_path}, 缓存目录: {cache_dir}")
    
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
    
    def get_cache_file(self, player_id):
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"player_{player_id}.json")
    
    def is_cache_valid(self, cache_file):
        """检查缓存是否有效"""
        if not os.path.exists(cache_file):
            return False
        
        # 检查文件修改时间
        mtime = os.path.getmtime(cache_file)
        current_time = time.time()
        
        return (current_time - mtime) < self.cache_expiry
    
    def load_cache(self, player_id):
        """加载缓存数据"""
        cache_file = self.get_cache_file(player_id)
        if self.is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"从缓存加载球员 {player_id} 的数据")
                return data
            except Exception as e:
                logger.error(f"加载缓存失败: {str(e)}")
        return None
    
    def save_cache(self, player_id, data):
        """保存缓存数据"""
        cache_file = self.get_cache_file(player_id)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"缓存球员 {player_id} 的数据")
        except Exception as e:
            logger.error(f"保存缓存失败: {str(e)}")
    
    def fetch_player_stats(self, player_id):
        """获取球员实时统计数据"""
        # 1. 首先检查缓存数据
        cached_data = self.load_cache(player_id)
        if cached_data:
            return cached_data
        
        # 2. 如果缓存过期，从API获取数据
        # 这里模拟API调用，实际项目中需要集成真实的API
        logger.info(f"从API获取球员 {player_id} 的实时数据")
        
        # 模拟数据
        player_stats = {
            'player_id': player_id,
            'name': f'Player {player_id}',
            'team': 'Test Team',
            'pos': 'OF',
            'stats': {
                'AVG': 0.275,
                'HR': 15,
                'RBI': 50,
                'R': 60,
                'SB': 10,
                'OBP': 0.350,
                'SLG': 0.450,
                'OPS': 0.800,
                'wRC+': 110,
                'WAR': 2.5
            },
            'statcast': {
                'exit_velocity': 90.5,
                'launch_angle': 15.0,
                'xwOBA': 0.340,
                'xBA': 0.280,
                'xSLG': 0.460,
                'hard_hit_rate': 0.35,
                'barrel_rate': 0.10,
                'chase_rate': 0.25,
                'swing_contact_rate': 0.80
            },
            'last_updated': datetime.now().isoformat()
        }
        
        # 3. 处理和转换数据格式
        # 这里可以添加数据转换逻辑
        
        # 4. 缓存数据
        self.save_cache(player_id, player_stats)
        
        # 5. 返回处理后的数据
        return player_stats
    
    def update_fa_pool(self):
        """更新FA池状态"""
        try:
            self.connect_db()
            
            # 1. 从联盟数据中获取当前FA池
            # 这里模拟获取FA池数据，实际项目中需要从真实数据源获取
            logger.info("更新FA池状态")
            
            # 模拟FA池数据
            fa_players = [
                {'player_id': 1, 'name': 'Mike Trout', 'team': 'LAA', 'pos': 'OF', 'status': 'available'},
                {'player_id': 2, 'name': 'Aaron Judge', 'team': 'NYY', 'pos': 'OF', 'status': 'available'},
                {'player_id': 3, 'name': 'Shohei Ohtani', 'team': 'LAD', 'pos': 'SP', 'status': 'available'},
                {'player_id': 4, 'name': 'Mookie Betts', 'team': 'LAD', 'pos': 'OF', 'status': 'available'},
                {'player_id': 5, 'name': 'Fernando Tatis Jr.', 'team': 'SD', 'pos': 'SS', 'status': 'available'}
            ]
            
            # 2. 与本地数据库对比并更新
            for player in fa_players:
                # 检查球员是否已在FA池中
                self.cursor.execute('''
                SELECT id FROM fa_pool WHERE player_id = ?
                ''', (player['player_id'],))
                existing = self.cursor.fetchone()
                
                if existing:
                    # 更新现有记录
                    self.cursor.execute('''
                    UPDATE fa_pool SET name = ?, team = ?, pos = ?, status = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE player_id = ?
                    ''', (player['name'], player['team'], player['pos'], player['status'], player['player_id']))
                else:
                    # 插入新记录
                    self.cursor.execute('''
                    INSERT INTO fa_pool (player_id, name, team, pos, status)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (player['player_id'], player['name'], player['team'], player['pos'], player['status']))
            
            self.conn.commit()
            logger.info(f"FA池更新完成，共更新 {len(fa_players)} 名球员")
            
            return fa_players
        except Exception as e:
            logger.error(f"更新FA池失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
    
    def update_injury_data(self):
        """更新伤病数据"""
        try:
            self.connect_db()
            
            # 1. 从可靠来源获取伤病报告
            # 这里模拟获取伤病数据，实际项目中需要从真实数据源获取
            logger.info("更新伤病数据")
            
            # 模拟伤病数据
            injury_reports = [
                {
                    'player_id': 1, 'name': 'Mike Trout', 'injury_type': 'Hamstring strain',
                    'severity': 'moderate', 'start_date': '2026-03-15', 'expected_return': '2026-04-01',
                    'status': 'injured'
                },
                {
                    'player_id': 3, 'name': 'Shohei Ohtani', 'injury_type': 'Elbow soreness',
                    'severity': 'mild', 'start_date': '2026-03-10', 'expected_return': '2026-03-25',
                    'status': 'day_to_day'
                }
            ]
            
            # 2. 解析伤病数据并更新数据库
            for injury in injury_reports:
                # 检查伤病报告是否已存在
                self.cursor.execute('''
                SELECT id FROM injury_reports WHERE player_id = ? AND injury_type = ? AND start_date = ?
                ''', (injury['player_id'], injury['injury_type'], injury['start_date']))
                existing = self.cursor.fetchone()
                
                if existing:
                    # 更新现有记录
                    self.cursor.execute('''
                    UPDATE injury_reports SET severity = ?, expected_return = ?, status = ?
                    WHERE id = ?
                    ''', (injury['severity'], injury['expected_return'], injury['status'], existing[0]))
                else:
                    # 插入新记录
                    self.cursor.execute('''
                    INSERT INTO injury_reports (player_id, name, injury_type, severity, start_date, expected_return, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        injury['player_id'], injury['name'], injury['injury_type'],
                        injury['severity'], injury['start_date'], injury['expected_return'], injury['status']
                    ))
            
            self.conn.commit()
            logger.info(f"伤病数据更新完成，共更新 {len(injury_reports)} 条伤病报告")
            
            return injury_reports
        except Exception as e:
            logger.error(f"更新伤病数据失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
    
    def import_data_from_file(self, file_path, data_type):
        """从文件导入数据
        
        Args:
            file_path: 文件路径
            data_type: 数据类型 ('fa_pool', 'player_stats', 'injury_reports')
        """
        try:
            self.connect_db()
            
            logger.info(f"从文件导入 {data_type} 数据: {file_path}")
            
            # 根据文件类型读取数据
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                df = pd.DataFrame(data)
            else:
                raise ValueError(f"不支持的文件格式: {file_path}")
            
            # 根据数据类型导入
            if data_type == 'fa_pool':
                for _, row in df.iterrows():
                    self.cursor.execute('''
                    INSERT OR REPLACE INTO fa_pool (player_id, name, team, pos, status, last_updated)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        row.get('player_id'), row.get('name'), row.get('team'),
                        row.get('pos'), row.get('status', 'available')
                    ))
            
            elif data_type == 'player_stats':
                for _, row in df.iterrows():
                    self.cursor.execute('''
                    INSERT INTO player_season_stats (player_id, name, team, pos, stat_type, value, game_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row.get('player_id'), row.get('name'), row.get('team'),
                        row.get('pos'), row.get('stat_type'), row.get('value'),
                        row.get('game_date', datetime.now().strftime('%Y-%m-%d'))
                    ))
            
            elif data_type == 'injury_reports':
                for _, row in df.iterrows():
                    self.cursor.execute('''
                    INSERT OR REPLACE INTO injury_reports (player_id, name, injury_type, severity, start_date, expected_return, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row.get('player_id'), row.get('name'), row.get('injury_type'),
                        row.get('severity'), row.get('start_date'), row.get('expected_return'),
                        row.get('status', 'injured')
                    ))
            
            self.conn.commit()
            logger.info(f"成功导入 {len(df)} 条 {data_type} 数据")
            
            return len(df)
        except Exception as e:
            logger.error(f"导入数据失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
    
    def get_fa_pool_stats(self, position=None):
        """获取FA池球员的统计数据
        
        Args:
            position: 位置筛选
        """
        try:
            self.connect_db()
            
            query = "SELECT * FROM fa_pool"
            params = []
            
            if position:
                query += " WHERE pos = ?"
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
            logger.error(f"获取FA池数据失败: {str(e)}")
            raise
        finally:
            self.disconnect_db()
