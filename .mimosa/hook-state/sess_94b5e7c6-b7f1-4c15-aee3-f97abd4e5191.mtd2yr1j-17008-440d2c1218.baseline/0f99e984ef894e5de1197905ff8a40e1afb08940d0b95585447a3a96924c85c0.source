#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据导入工具
负责将手动下载的CSV文件导入到SQLite数据库中
支持多源预测数据的融合
"""

import os
import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Tuple
from config_loader import get_config

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('ingest_manual_csv')


class DataIngestor:
    """数据导入器类"""
    
    def __init__(self, db_path: str = 'fantasy_baseball.db'):
        """
        初始化数据导入器
        
        Args:
            db_path: 数据库文件路径
        """
        logger.info(f"初始化DataIngestor，数据库路径: {db_path}")
        self.db_path = db_path
        self.config = get_config()
        self.conn = None
        self.cursor = None
        logger.info("配置加载完成")
    
    def connect_db(self) -> None:
        """
        连接到SQLite数据库
        """
        logger.info(f"连接到数据库: {self.db_path}")
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logger.info("数据库连接成功")
            logger.info("开始创建数据表...")
            self._create_tables()
            logger.info("数据表创建完成")
        except Exception as e:
            logger.error(f"数据库操作失败: {str(e)}")
            raise
    
    def disconnect_db(self) -> None:
        """
        断开数据库连接
        """
        if self.conn:
            self.conn.commit()
            self.conn.close()
    
    def _create_tables(self) -> None:
        """
        创建数据库表
        """
        # 创建打者表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS hitters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            team TEXT,
            pos TEXT,
            source TEXT,
            R REAL,
            HR REAL,
            RBI REAL,
            SB REAL,
            AVG REAL,
            OBP REAL,
            SLG REAL,
            OPS REAL,
            PA REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建投手表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS pitchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            team TEXT,
            pos TEXT,
            source TEXT,
            W REAL,
            L REAL,
            SV REAL,
            HOLD REAL,
            ERA REAL,
            WHIP REAL,
            K_per_9 REAL,
            BB_per_9 REAL,
            IP REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建球员位置表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            pos TEXT,
            team TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 创建融合后的数据表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS hitters_merged (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            team TEXT,
            pos TEXT,
            R REAL,
            HR REAL,
            RBI REAL,
            SB REAL,
            AVG REAL,
            OBP REAL,
            SLG REAL,
            OPS REAL,
            PA REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS pitchers_merged (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            team TEXT,
            pos TEXT,
            W REAL,
            L REAL,
            SV REAL,
            HOLD REAL,
            ERA REAL,
            WHIP REAL,
            K_per_9 REAL,
            BB_per_9 REAL,
            IP REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    def ingest_positions(self) -> None:
        """
        导入球员位置数据
        """
        positions_file = self.config['data']['positions_file']
        logger.info(f"开始导入球员位置数据，文件路径: {positions_file}")
        
        if not os.path.exists(positions_file):
            warning_msg = f"位置映射文件不存在: {positions_file}"
            logger.warning(warning_msg)
            print(f"警告: {warning_msg}")
            return
        
        try:
            df = pd.read_csv(positions_file)
            logger.info(f"成功加载位置数据文件: {len(df)} 行数据")
            
            # 确保必要的列存在
            if 'Name' not in df.columns or 'POS' not in df.columns:
                error_msg = "位置映射文件必须包含 'Name' 和 'POS' 列"
                logger.error(error_msg)
                print(f"错误: {error_msg}")
                return
            
            # 清理数据
            df = df[['Name', 'POS']].dropna()
            df['Name'] = df['Name'].str.strip()
            df['POS'] = df['POS'].str.strip()
            logger.info(f"数据清理完成: {len(df)} 条有效数据")
            
            # 插入数据
            success_count = 0
            error_count = 0
            for _, row in df.iterrows():
                try:
                    self.cursor.execute(
                        "INSERT OR REPLACE INTO player_positions (name, pos) VALUES (?, ?)",
                        (row['Name'], row['POS'])
                    )
                    success_count += 1
                except Exception as e:
                    error_msg = f"插入位置数据失败 for {row['Name']}: {e}"
                    logger.warning(error_msg)
                    print(f"警告: {error_msg}")
                    error_count += 1
            
            logger.info(f"位置数据导入完成: 成功 {success_count} 条, 失败 {error_count} 条")
            print(f"成功导入 {success_count} 条位置数据")
            
        except Exception as e:
            error_msg = f"导入位置数据失败: {e}"
            logger.error(error_msg)
            print(f"错误: {error_msg}")
    
    def ingest_hitters(self) -> None:
        """
        导入打者数据
        """
        use_multi_source = self.config['data']['use_multi_source']
        logger.info(f"开始导入打者数据，多源模式: {use_multi_source}")
        
        if use_multi_source:
            # 多源导入
            sources = self.config['projections']['sources']
            file_pattern = self.config['data']['file_patterns']['hitters']
            logger.info(f"多源导入模式: {len(sources)} 个数据源")
            
            for source in sources:
                file_path = os.path.join('data', file_pattern.format(source=source.lower()))
                if os.path.exists(file_path):
                    logger.info(f"处理打者数据文件: {file_path}")
                    self._ingest_single_source(file_path, 'hitters', source)
                else:
                    warning_msg = f"打者数据文件不存在: {file_path}"
                    logger.warning(warning_msg)
                    print(f"警告: {warning_msg}")
        else:
            # 单源导入
            file_path = os.path.join('data', 'hitters_2026.csv')
            if os.path.exists(file_path):
                logger.info(f"处理单源打者数据文件: {file_path}")
                self._ingest_single_source(file_path, 'hitters', 'SINGLE')
            else:
                warning_msg = f"打者数据文件不存在: {file_path}"
                logger.warning(warning_msg)
                print(f"警告: {warning_msg}")
        logger.info("打者数据导入完成")
    
    def ingest_pitchers(self) -> None:
        """
        导入投手数据
        """
        use_multi_source = self.config['data']['use_multi_source']
        logger.info(f"开始导入投手数据，多源模式: {use_multi_source}")
        
        if use_multi_source:
            # 多源导入
            sources = self.config['projections']['sources']
            file_pattern = self.config['data']['file_patterns']['pitchers']
            logger.info(f"多源导入模式: {len(sources)} 个数据源")
            
            for source in sources:
                file_path = os.path.join('data', file_pattern.format(source=source.lower()))
                if os.path.exists(file_path):
                    logger.info(f"处理投手数据文件: {file_path}")
                    self._ingest_single_source(file_path, 'pitchers', source)
                else:
                    warning_msg = f"投手数据文件不存在: {file_path}"
                    logger.warning(warning_msg)
                    print(f"警告: {warning_msg}")
        else:
            # 单源导入
            file_path = os.path.join('data', 'pitchers_2026.csv')
            if os.path.exists(file_path):
                logger.info(f"处理单源投手数据文件: {file_path}")
                self._ingest_single_source(file_path, 'pitchers', 'SINGLE')
            else:
                warning_msg = f"投手数据文件不存在: {file_path}"
                logger.warning(warning_msg)
                print(f"警告: {warning_msg}")
        logger.info("投手数据导入完成")
    
    def _ingest_single_source(self, file_path: str, player_type: str, source: str) -> None:
        """
        导入单个源的数据
        
        Args:
            file_path: 文件路径
            player_type: 球员类型 ('hitters' 或 'pitchers')
            source: 数据来源
        """
        logger.info(f"开始导入 {source} 的 {player_type} 数据: {file_path}")
        print(f"正在导入 {source} 的 {player_type} 数据: {file_path}")
        
        try:
            df = pd.read_csv(file_path)
            logger.info(f"成功加载数据文件: {len(df)} 行数据")
            
            # 清理列名
            df.columns = [col.strip() for col in df.columns]
            logger.info("列名清理完成")
            
            # 映射列名
            if player_type == 'hitters':
                self._map_hitter_columns(df, source)
            else:
                self._map_pitcher_columns(df, source)
                
        except Exception as e:
            error_msg = f"导入 {file_path} 失败: {e}"
            logger.error(error_msg)
            print(f"错误: {error_msg}")
    
    def _map_hitter_columns(self, df: pd.DataFrame, source: str) -> None:
        """
        映射打者列名并导入数据
        
        Args:
            df: 打者数据DataFrame
            source: 数据来源
        """
        logger.info(f"开始映射 {source} 打者列名")
        
        # 常见列名映射
        column_mappings = {
            'Name': 'name',
            'Team': 'team',
            'POS': 'pos',
            'R': 'R',
            'HR': 'HR',
            'RBI': 'RBI',
            'SB': 'SB',
            'AVG': 'AVG',
            'OBP': 'OBP',
            'SLG': 'SLG',
            'OPS': 'OPS',
            'PA': 'PA'
        }
        
        # 重命名列
        mapped_df = pd.DataFrame()
        missing_columns = []
        for csv_col, db_col in column_mappings.items():
            if csv_col in df.columns:
                mapped_df[db_col] = df[csv_col]
            else:
                mapped_df[db_col] = None
                missing_columns.append(csv_col)
        
        if missing_columns:
            logger.warning(f"{source} 打者数据缺少列: {missing_columns}")
        
        # 添加source列
        mapped_df['source'] = source
        
        # 清理数据
        mapped_df = mapped_df.dropna(subset=['name'])
        mapped_df['name'] = mapped_df['name'].str.strip()
        logger.info(f"{source} 打者数据清理完成: {len(mapped_df)} 条有效数据")
        
        # 插入数据
        success_count = 0
        error_count = 0
        for _, row in mapped_df.iterrows():
            try:
                self.cursor.execute(
                    '''INSERT OR REPLACE INTO hitters 
                    (name, team, pos, source, R, HR, RBI, SB, AVG, OBP, SLG, OPS, PA) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['name'], row['team'], row['pos'], row['source'],
                     row['R'], row['HR'], row['RBI'], row['SB'],
                     row['AVG'], row['OBP'], row['SLG'], row['OPS'], row['PA'])
                )
                success_count += 1
            except Exception as e:
                error_msg = f"插入打者数据失败 for {row['name']}: {e}"
                logger.warning(error_msg)
                print(f"警告: {error_msg}")
                error_count += 1
        
        logger.info(f"{source} 打者数据导入完成: 成功 {success_count} 条, 失败 {error_count} 条")
        print(f"成功导入 {success_count} 条打者数据 from {source}")
    
    def _map_pitcher_columns(self, df: pd.DataFrame, source: str) -> None:
        """
        映射投手列名并导入数据
        
        Args:
            df: 投手数据DataFrame
            source: 数据来源
        """
        logger.info(f"开始映射 {source} 投手列名")
        
        # 常见列名映射
        column_mappings = {
            'Name': 'name',
            'Team': 'team',
            'POS': 'pos',
            'W': 'W',
            'L': 'L',
            'SV': 'SV',
            'HOLD': 'HOLD',
            'ERA': 'ERA',
            'WHIP': 'WHIP',
            'K/9': 'K_per_9',
            'BB/9': 'BB_per_9',
            'IP': 'IP'
        }
        
        # 重命名列
        mapped_df = pd.DataFrame()
        missing_columns = []
        for csv_col, db_col in column_mappings.items():
            if csv_col in df.columns:
                mapped_df[db_col] = df[csv_col]
            else:
                mapped_df[db_col] = None
                missing_columns.append(csv_col)
        
        if missing_columns:
            logger.warning(f"{source} 投手数据缺少列: {missing_columns}")
        
        # 添加source列
        mapped_df['source'] = source
        
        # 清理数据
        mapped_df = mapped_df.dropna(subset=['name'])
        mapped_df['name'] = mapped_df['name'].str.strip()
        logger.info(f"{source} 投手数据清理完成: {len(mapped_df)} 条有效数据")
        
        # 插入数据
        success_count = 0
        error_count = 0
        for _, row in mapped_df.iterrows():
            try:
                self.cursor.execute(
                    '''INSERT OR REPLACE INTO pitchers 
                    (name, team, pos, source, W, L, SV, HOLD, ERA, WHIP, K_per_9, BB_per_9, IP) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['name'], row['team'], row['pos'], row['source'],
                     row['W'], row['L'], row['SV'], row['HOLD'],
                     row['ERA'], row['WHIP'], row['K_per_9'], row['BB_per_9'], row['IP'])
                )
                success_count += 1
            except Exception as e:
                error_msg = f"插入投手数据失败 for {row['name']}: {e}"
                logger.warning(error_msg)
                print(f"警告: {error_msg}")
                error_count += 1
        
        logger.info(f"{source} 投手数据导入完成: 成功 {success_count} 条, 失败 {error_count} 条")
        print(f"成功导入 {success_count} 条投手数据 from {source}")
    
    def merge_data(self) -> None:
        """
        融合多源数据
        """
        logger.info("开始融合数据...")
        
        if self.config['data']['use_multi_source']:
            logger.info("执行多源数据融合")
            logger.info("开始融合打者数据...")
            self._merge_hitters()
            logger.info("打者数据融合完成")
            
            logger.info("开始融合投手数据...")
            self._merge_pitchers()
            logger.info("投手数据融合完成")
        else:
            # 单源数据直接复制
            logger.info("执行单源数据复制")
            self._copy_single_source_data()
        
        logger.info("数据融合完成")
    
    def _merge_hitters(self) -> None:
        """
        融合打者数据
        """
        # 获取权重
        weights = self.config['projections']['weights']
        
        # 获取所有打者数据
        hitters_df = pd.read_sql_query("SELECT * FROM hitters", self.conn)
        
        if hitters_df.empty:
            print("警告: 没有打者数据可融合")
            return
        
        # 按球员分组
        grouped = hitters_df.groupby('name')
        
        # 融合数据
        merged_data = []
        for name, group in grouped:
            merged_row = {'name': name}
            
            # 获取球队和位置（使用第一个非空值）
            merged_row['team'] = group['team'].dropna().iloc[0] if not group['team'].dropna().empty else None
            merged_row['pos'] = group['pos'].dropna().iloc[0] if not group['pos'].dropna().empty else None
            
            # 加权平均统计项
            stats_cols = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG', 'OPS', 'PA']
            for col in stats_cols:
                weighted_sum = 0
                total_weight = 0
                
                for _, row in group.iterrows():
                    source = row['source']
                    weight = weights.get(source, 0)
                    value = row[col]
                    
                    if pd.notna(value) and weight > 0:
                        weighted_sum += value * weight
                        total_weight += weight
                
                if total_weight > 0:
                    merged_row[col] = weighted_sum / total_weight
                else:
                    merged_row[col] = None
            
            merged_data.append(merged_row)
        
        # 插入融合后的数据
        for row in merged_data:
            try:
                self.cursor.execute(
                    '''INSERT OR REPLACE INTO hitters_merged 
                    (name, team, pos, R, HR, RBI, SB, AVG, OBP, SLG, OPS, PA) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['name'], row['team'], row['pos'], row['R'], row['HR'], row['RBI'], 
                     row['SB'], row['AVG'], row['OBP'], row['SLG'], row['OPS'], row['PA'])
                )
            except Exception as e:
                print(f"警告: 插入融合打者数据失败 for {row['name']}: {e}")
        
        print(f"成功融合 {len(merged_data)} 条打者数据")
    
    def _merge_pitchers(self) -> None:
        """
        融合投手数据
        """
        # 获取权重
        weights = self.config['projections']['weights']
        
        # 获取所有投手数据
        pitchers_df = pd.read_sql_query("SELECT * FROM pitchers", self.conn)
        
        if pitchers_df.empty:
            print("警告: 没有投手数据可融合")
            return
        
        # 按球员分组
        grouped = pitchers_df.groupby('name')
        
        # 融合数据
        merged_data = []
        for name, group in grouped:
            merged_row = {'name': name}
            
            # 获取球队和位置（使用第一个非空值）
            merged_row['team'] = group['team'].dropna().iloc[0] if not group['team'].dropna().empty else None
            merged_row['pos'] = group['pos'].dropna().iloc[0] if not group['pos'].dropna().empty else None
            
            # 加权平均统计项
            stats_cols = ['W', 'L', 'SV', 'HOLD', 'ERA', 'WHIP', 'K_per_9', 'BB_per_9', 'IP']
            for col in stats_cols:
                weighted_sum = 0
                total_weight = 0
                
                for _, row in group.iterrows():
                    source = row['source']
                    weight = weights.get(source, 0)
                    value = row[col]
                    
                    if pd.notna(value) and weight > 0:
                        weighted_sum += value * weight
                        total_weight += weight
                
                if total_weight > 0:
                    merged_row[col] = weighted_sum / total_weight
                else:
                    merged_row[col] = None
            
            merged_data.append(merged_row)
        
        # 插入融合后的数据
        for row in merged_data:
            try:
                self.cursor.execute(
                    '''INSERT OR REPLACE INTO pitchers_merged 
                    (name, team, pos, W, L, SV, HOLD, ERA, WHIP, K_per_9, BB_per_9, IP) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['name'], row['team'], row['pos'], row['W'], row['L'], row['SV'], 
                     row['HOLD'], row['ERA'], row['WHIP'], row['K_per_9'], row['BB_per_9'], row['IP'])
                )
            except Exception as e:
                print(f"警告: 插入融合投手数据失败 for {row['name']}: {e}")
        
        print(f"成功融合 {len(merged_data)} 条投手数据")
    
    def _copy_single_source_data(self) -> None:
        """
        复制单源数据到融合表
        """
        # 复制打者数据
        self.cursor.execute('''
        INSERT OR REPLACE INTO hitters_merged (name, team, pos, R, HR, RBI, SB, AVG, OBP, SLG, OPS, PA)
        SELECT name, team, pos, R, HR, RBI, SB, AVG, OBP, SLG, OPS, PA
        FROM hitters
        WHERE source = 'SINGLE'
        ''')
        
        # 复制投手数据
        self.cursor.execute('''
        INSERT OR REPLACE INTO pitchers_merged (name, team, pos, W, L, SV, HOLD, ERA, WHIP, K_per_9, BB_per_9, IP)
        SELECT name, team, pos, W, L, SV, HOLD, ERA, WHIP, K_per_9, BB_per_9, IP
        FROM pitchers
        WHERE source = 'SINGLE'
        ''')
        
        print("成功复制单源数据到融合表")


def main():
    """
    主函数
    """
    logger.info("=========================================")
    logger.info("开始执行 Fantasy Baseball 数据导入工具")
    logger.info("=========================================")
    
    print("=== Fantasy Baseball 数据导入工具 ===")
    
    # 创建数据导入器
    logger.info("创建数据导入器实例")
    ingestor = DataIngestor()
    
    try:
        # 连接数据库
        logger.info("连接数据库")
        ingestor.connect_db()
        
        # 导入位置数据
        logger.info("开始导入球员位置数据")
        print("\n1. 导入球员位置数据...")
        ingestor.ingest_positions()
        
        # 导入打者数据
        logger.info("开始导入打者数据")
        print("\n2. 导入打者数据...")
        ingestor.ingest_hitters()
        
        # 导入投手数据
        logger.info("开始导入投手数据")
        print("\n3. 导入投手数据...")
        ingestor.ingest_pitchers()
        
        # 融合数据
        logger.info("开始融合多源数据")
        print("\n4. 融合多源数据...")
        ingestor.merge_data()
        
        logger.info("数据导入和融合完成！")
        print("\n✅ 数据导入和融合完成！")
        
    except Exception as e:
        error_msg = f"执行过程中出错: {str(e)}"
        logger.error(error_msg)
        print(f"\n❌ 错误: {e}")
    finally:
        # 断开数据库连接
        logger.info("断开数据库连接")
        ingestor.disconnect_db()
    
    logger.info("=========================================")
    logger.info("Fantasy Baseball 数据导入工具执行完成")
    logger.info("=========================================")


if __name__ == '__main__':
    main()
