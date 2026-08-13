#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建FA分析所需的数据库表结构
"""

import sqlite3

def create_fa_tables():
    """创建FA分析所需的数据库表"""
    try:
        conn = sqlite3.connect('fantasy_baseball.db')
        cursor = conn.cursor()
        
        print("开始创建FA分析相关表结构...")
        
        # 创建FA池表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fa_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            team TEXT,
            pos TEXT,
            status TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES hitters(id) ON DELETE SET NULL
        )
        ''')
        print("✓ 创建fa_pool表成功")
        
        # 创建球员赛季统计表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_season_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            team TEXT,
            pos TEXT,
            stat_type TEXT,
            value REAL,
            game_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES hitters(id) ON DELETE SET NULL
        )
        ''')
        print("✓ 创建player_season_stats表成功")
        
        # 创建用户阵容表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_roster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            team TEXT,
            pos TEXT,
            status TEXT,
            acquisition_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES hitters(id) ON DELETE SET NULL
        )
        ''')
        print("✓ 创建user_roster表成功")
        
        # 创建伤病报告表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS injury_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            injury_type TEXT,
            severity TEXT,
            start_date DATE,
            expected_return DATE,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES hitters(id) ON DELETE SET NULL
        )
        ''')
        print("✓ 创建injury_reports表成功")
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fa_pool_pos ON fa_pool(pos)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_season_stats_player ON player_season_stats(player_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_roster_pos ON user_roster(pos)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_injury_reports_player ON injury_reports(player_id)')
        print("✓ 创建索引成功")
        
        conn.commit()
        print("\n✅ 所有表结构创建完成！")
        
        # 查看创建的表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\n数据库中的表:")
        for table in tables:
            print(f"- {table[0]}")
        
        conn.close()
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == '__main__':
    create_fa_tables()
