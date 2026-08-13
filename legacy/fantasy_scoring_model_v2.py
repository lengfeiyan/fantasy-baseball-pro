#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分模型工具
负责计算球员的VORP（Value Over Replacement Player）和风险评分
生成带风险评分的排名文件
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from config_loader import get_config

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('fantasy_scoring_model')


class FantasyScoringModel:
    """Fantasy Baseball评分模型类"""
    
    def __init__(self, db_path: str = 'fantasy_baseball.db'):
        """
        初始化评分模型
        
        Args:
            db_path: 数据库文件路径
        """
        logger.info(f"初始化FantasyScoringModel，数据库路径: {db_path}")
        self.db_path = db_path
        self.config = get_config()
        self.conn = None
        self.cursor = None
        self.scoring_rules = self.config['league']['scoring']
        self.risk_method = self.config['risk_model']['method']
        self.risk_adjustment = self.config['risk_model']['adjustment_factor']
        logger.info(f"评分规则加载完成: 打者规则={len(self.scoring_rules.get('hitters', {}))}项, 投手规则={len(self.scoring_rules.get('pitchers', {}))}项")
        logger.info(f"风险模型配置: 方法={self.risk_method}, 调整因子={self.risk_adjustment}")
    
    def connect_db(self) -> None:
        """
        连接到SQLite数据库
        """
        logger.info(f"连接到数据库: {self.db_path}")
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            raise
    
    def disconnect_db(self) -> None:
        """
        断开数据库连接
        """
        if self.conn:
            self.conn.close()
    
    def calculate_vorp(self) -> pd.DataFrame:
        """
        计算所有球员的VORP
        
        Returns:
            包含VORP和风险评分的DataFrame
        """
        logger.info("开始计算所有球员的VORP...")
        
        # 获取融合后的打者数据
        logger.info("获取融合后的打者数据...")
        hitters_df = pd.read_sql_query("SELECT * FROM hitters_merged", self.conn)
        logger.info(f"打者数据加载完成: {len(hitters_df)} 名打者")
        
        # 获取融合后的投手数据
        logger.info("获取融合后的投手数据...")
        pitchers_df = pd.read_sql_query("SELECT * FROM pitchers_merged", self.conn)
        logger.info(f"投手数据加载完成: {len(pitchers_df)} 名投手")
        
        if hitters_df.empty and pitchers_df.empty:
            error_msg = "没有数据可计算VORP"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 计算打者VORP
        if not hitters_df.empty:
            logger.info("开始计算打者VORP...")
            hitters_df = self._calculate_hitter_vorp(hitters_df)
            logger.info("打者VORP计算完成")
        
        # 计算投手VORP
        if not pitchers_df.empty:
            logger.info("开始计算投手VORP...")
            pitchers_df = self._calculate_pitcher_vorp(pitchers_df)
            logger.info("投手VORP计算完成")
        
        # 合并数据
        logger.info("合并打者和投手数据...")
        if not hitters_df.empty and not pitchers_df.empty:
            all_players_df = pd.concat([hitters_df, pitchers_df], ignore_index=True)
            logger.info(f"成功合并 {len(hitters_df)} 名打者和 {len(pitchers_df)} 名投手的数据")
        elif not hitters_df.empty:
            all_players_df = hitters_df
            logger.info(f"仅使用打者数据: {len(hitters_df)} 名打者")
        else:
            all_players_df = pitchers_df
            logger.info(f"仅使用投手数据: {len(pitchers_df)} 名投手")
        
        # 计算风险评分
        logger.info("开始计算风险评分...")
        all_players_df = self._calculate_risk_scores(all_players_df)
        logger.info("风险评分计算完成")
        
        # 排序
        logger.info("按VORP排序球员...")
        all_players_df = all_players_df.sort_values('vorp', ascending=False)
        
        # 添加排名
        all_players_df['rank'] = range(1, len(all_players_df) + 1)
        logger.info(f"VORP计算完成，共处理 {len(all_players_df)} 名球员")
        
        return all_players_df
    
    def _calculate_hitter_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算打者VORP
        
        Args:
            df: 打者数据DataFrame
            
        Returns:
            包含VORP的打者DataFrame
        """
        # 计算基础分数
        df['score'] = 0
        
        # 应用评分规则
        for stat, weight in self.scoring_rules['hitters'].items():
            if stat in df.columns:
                df['score'] += df[stat] * weight
        
        # 计算替代球员水平（取每个位置后25%球员的平均分数）
        replacement_levels = {}
        for pos in df['pos'].unique():
            pos_players = df[df['pos'] == pos]
            if len(pos_players) > 0:
                replacement_level = pos_players['score'].quantile(0.25)
                replacement_levels[pos] = replacement_level
        
        # 计算VORP
        df['vorp'] = df.apply(lambda row: row['score'] - replacement_levels.get(row['pos'], 0), axis=1)
        
        # 标记球员类型
        df['player_type'] = 'hitter'
        
        return df
    
    def _calculate_pitcher_vorp(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算投手VORP
        
        Args:
            df: 投手数据DataFrame
            
        Returns:
            包含VORP的投手DataFrame
        """
        # 计算基础分数
        df['score'] = 0
        
        # 应用评分规则
        for stat, weight in self.scoring_rules['pitchers'].items():
            if stat in df.columns:
                df['score'] += df[stat] * weight
        
        # 计算替代球员水平（取后25%球员的平均分数）
        replacement_level = df['score'].quantile(0.25)
        
        # 计算VORP
        df['vorp'] = df['score'] - replacement_level
        
        # 标记球员类型
        df['player_type'] = 'pitcher'
        
        return df
    
    def _calculate_risk_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算风险评分
        
        Args:
            df: 球员数据DataFrame
            
        Returns:
            包含风险评分的球员DataFrame
        """
        if self.risk_method == 'z_score':
            # 使用Z-score方法计算风险
            for player_type in ['hitter', 'pitcher']:
                type_df = df[df['player_type'] == player_type]
                if len(type_df) > 1:
                    # 计算VORP的标准差
                    std_dev = type_df['vorp'].std()
                    
                    # 计算上下限
                    df.loc[df['player_type'] == player_type, 'vorp_upside'] = \
                        df.loc[df['player_type'] == player_type, 'vorp'] + std_dev * self.risk_adjustment
                    df.loc[df['player_type'] == player_type, 'vorp_floor'] = \
                        df.loc[df['player_type'] == player_type, 'vorp'] - std_dev * self.risk_adjustment
        elif self.risk_method == 'historical_variance':
            # 使用历史方差方法计算风险（这里简化处理，实际应该使用历史数据）
            df['vorp_upside'] = df['vorp'] * (1 + self.risk_adjustment)
            df['vorp_floor'] = df['vorp'] * (1 - self.risk_adjustment)
        else:
            # 默认方法
            df['vorp_upside'] = df['vorp'] * 1.1
            df['vorp_floor'] = df['vorp'] * 0.9
        
        # 确保floor不为负
        df['vorp_floor'] = df['vorp_floor'].clip(lower=0)
        
        return df
    
    def generate_rankings(self, output_file: str = 'fantasy_draft_rankings_vorp_2026.csv') -> None:
        """
        生成排名文件
        
        Args:
            output_file: 输出文件路径
        """
        logger.info(f"开始生成排名文件: {output_file}")
        
        # 计算VORP和风险评分
        rankings_df = self.calculate_vorp()
        
        # 选择需要的列
        columns_to_keep = [
            'rank', 'name', 'team', 'pos', 'player_type', 'vorp', 
            'vorp_upside', 'vorp_floor', 'score'
        ]
        
        # 确保所有列都存在
        logger.info("检查并确保所有必要列存在...")
        for col in columns_to_keep:
            if col not in rankings_df.columns:
                rankings_df[col] = None
                logger.warning(f"列 {col} 不存在，设置为None")
        
        # 重排列
        rankings_df = rankings_df[columns_to_keep]
        logger.info(f"数据处理完成，保留 {len(columns_to_keep)} 列")
        
        # 保存到CSV
        logger.info(f"保存排名文件到: {output_file}")
        try:
            rankings_df.to_csv(output_file, index=False)
            logger.info(f"成功保存排名文件: {output_file}")
        except Exception as e:
            logger.error(f"保存排名文件失败: {str(e)}")
            raise
        
        print(f"✅ 成功生成排名文件: {output_file}")
        print(f"📊 共包含 {len(rankings_df)} 名球员")
        print(f"🏆 排名第一: {rankings_df.iloc[0]['name']} (VORP: {rankings_df.iloc[0]['vorp']:.2f})")
        
        logger.info(f"排名文件生成完成:")
        logger.info(f"- 文件路径: {output_file}")
        logger.info(f"- 球员数量: {len(rankings_df)}")
        logger.info(f"- 排名第一: {rankings_df.iloc[0]['name']} (VORP: {rankings_df.iloc[0]['vorp']:.2f})")


def main():
    """
    主函数
    """
    logger.info("=========================================")
    logger.info("开始执行 Fantasy Baseball 评分模型工具")
    logger.info("=========================================")
    
    print("=== Fantasy Baseball 评分模型工具 ===")
    
    # 创建评分模型
    logger.info("创建评分模型实例")
    model = FantasyScoringModel()
    
    try:
        # 连接数据库
        logger.info("连接数据库")
        model.connect_db()
        
        # 生成排名
        logger.info("开始生成排名")
        model.generate_rankings()
        
    except Exception as e:
        error_msg = f"执行过程中出错: {str(e)}"
        logger.error(error_msg)
        print(f"\n❌ 错误: {e}")
    finally:
        # 断开数据库连接
        logger.info("断开数据库连接")
        model.disconnect_db()
    
    logger.info("=========================================")
    logger.info("Fantasy Baseball 评分模型工具执行完成")
    logger.info("=========================================")


if __name__ == '__main__':
    main()
