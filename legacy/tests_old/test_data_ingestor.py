#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据导入器测试
"""

import os
import tempfile
import sqlite3
import pandas as pd
import unittest
from ingest_manual_csv_to_db import DataIngestor


class TestDataIngestor(unittest.TestCase):
    """数据导入器测试类"""
    
    def setUp(self):
        """
        测试前准备
        """
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # 创建测试数据目录
        self.test_data_dir = tempfile.mkdtemp()
        
        # 创建测试位置映射文件
        self.positions_file = os.path.join(self.test_data_dir, 'player_positions_2025.csv')
        positions_data = pd.DataFrame({
            'Name': ['Ronald Acuña Jr.', 'Shohei Ohtani', 'Mookie Betts'],
            'POS': ['OF', 'DH', 'OF']
        })
        positions_data.to_csv(self.positions_file, index=False)
        
        # 创建测试打者数据文件
        self.hitters_file = os.path.join(self.test_data_dir, 'hitters_2026_steamer.csv')
        hitters_data = pd.DataFrame({
            'Name': ['Ronald Acuña Jr.', 'Mookie Betts', 'Mike Trout'],
            'Team': ['ATL', 'LAD', 'LAA'],
            'POS': ['OF', 'OF', 'OF'],
            'R': [100, 90, 85],
            'HR': [40, 35, 30],
            'RBI': [100, 95, 80],
            'SB': [30, 15, 10],
            'AVG': [0.300, 0.290, 0.280],
            'OBP': [0.400, 0.380, 0.370],
            'SLG': [0.600, 0.580, 0.550],
            'OPS': [1.000, 0.960, 0.920],
            'PA': [600, 580, 550]
        })
        hitters_data.to_csv(self.hitters_file, index=False)
        
        # 创建测试投手数据文件
        self.pitchers_file = os.path.join(self.test_data_dir, 'pitchers_2026_steamer.csv')
        pitchers_data = pd.DataFrame({
            'Name': ['Gerrit Cole', 'Max Scherzer', 'Jacob deGrom'],
            'Team': ['NYY', 'TEX', 'TEX'],
            'POS': ['SP', 'SP', 'SP'],
            'W': [18, 16, 15],
            'L': [6, 8, 7],
            'SV': [0, 0, 0],
            'HOLD': [0, 0, 0],
            'ERA': [2.50, 2.70, 2.60],
            'WHIP': [1.00, 1.05, 1.02],
            'K/9': [12.0, 11.5, 12.5],
            'BB/9': [2.0, 2.2, 1.8],
            'IP': [200, 190, 180]
        })
        pitchers_data.to_csv(self.pitchers_file, index=False)
    
    def tearDown(self):
        """
        测试后清理
        """
        # 删除临时数据库文件
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
        
        # 删除测试数据目录
        if os.path.exists(self.test_data_dir):
            import shutil
            shutil.rmtree(self.test_data_dir)
    
    def test_connect_db(self):
        """
        测试连接数据库
        """
        ingestor = DataIngestor(self.temp_db_path)
        ingestor.connect_db()
        
        # 验证数据库连接成功
        self.assertIsNotNone(ingestor.conn)
        self.assertIsNotNone(ingestor.cursor)
        
        # 验证表创建成功
        ingestor.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in ingestor.cursor.fetchall()]
        expected_tables = ['hitters', 'pitchers', 'player_positions', 'hitters_merged', 'pitchers_merged']
        for table in expected_tables:
            self.assertIn(table, tables)
        
        ingestor.disconnect_db()
    
    def test_ingest_positions(self):
        """
        测试导入位置数据
        """
        ingestor = DataIngestor(self.temp_db_path)
        ingestor.connect_db()
        
        # 修改配置中的位置映射文件路径
        import config_loader
        config = config_loader.get_config()
        config['data']['positions_file'] = self.positions_file
        
        # 导入位置数据
        ingestor.ingest_positions()
        
        # 验证数据导入成功
        positions_df = pd.read_sql_query("SELECT * FROM player_positions", ingestor.conn)
        self.assertEqual(len(positions_df), 3)
        self.assertIn('Ronald Acuña Jr.', positions_df['name'].values)
        
        ingestor.disconnect_db()
    
    def test_ingest_hitters(self):
        """
        测试导入打者数据
        """
        ingestor = DataIngestor(self.temp_db_path)
        ingestor.connect_db()
        
        # 修改配置中的数据文件路径
        import config_loader
        config = config_loader.get_config()
        config['data']['file_patterns']['hitters'] = os.path.basename(self.hitters_file)
        
        # 复制文件到当前目录
        import shutil
        shutil.copy(self.hitters_file, '.')
        
        try:
            # 导入打者数据
            ingestor.ingest_hitters()
            
            # 验证数据导入成功
            hitters_df = pd.read_sql_query("SELECT * FROM hitters", ingestor.conn)
            self.assertEqual(len(hitters_df), 3)
            self.assertIn('Ronald Acuña Jr.', hitters_df['name'].values)
        finally:
            # 清理复制的文件
            if os.path.exists(os.path.basename(self.hitters_file)):
                os.unlink(os.path.basename(self.hitters_file))
        
        ingestor.disconnect_db()
    
    def test_merge_data(self):
        """
        测试融合数据
        """
        ingestor = DataIngestor(self.temp_db_path)
        ingestor.connect_db()
        
        # 修改配置中的数据文件路径
        import config_loader
        config = config_loader.get_config()
        config['data']['use_multi_source'] = False
        
        # 复制文件到当前目录
        import shutil
        single_hitters_file = 'hitters_2026.csv'
        shutil.copy(self.hitters_file, single_hitters_file)
        
        try:
            # 导入打者数据
            ingestor.ingest_hitters()
            
            # 融合数据
            ingestor.merge_data()
            
            # 验证数据融合成功
            merged_df = pd.read_sql_query("SELECT * FROM hitters_merged", ingestor.conn)
            self.assertEqual(len(merged_df), 3)
            self.assertIn('Ronald Acuña Jr.', merged_df['name'].values)
        finally:
            # 清理复制的文件
            if os.path.exists(single_hitters_file):
                os.unlink(single_hitters_file)
        
        ingestor.disconnect_db()


if __name__ == '__main__':
    unittest.main()
