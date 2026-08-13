#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fantasy Baseball Sleeper 推荐器 - 基础版
基于 VORP vs ADP 偏差 识别被市场低估的球员
"""

import os
import sys
import argparse
import pandas as pd

# 添加日志功能
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('find_sleeper_players')


def load_data():
    """
    加载必要的数据文件
    """
    logger.info("开始加载数据...")
    
    # 检查数据文件是否存在
    rankings_file = 'fantasy_draft_rankings_vorp_2026.csv'
    adp_file = 'adp.csv'
    
    if not os.path.exists(rankings_file):
        error_msg = f"{rankings_file} 文件不存在，请先运行 fantasy_scoring_model_v2.py"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
        sys.exit(1)
    
    if not os.path.exists(adp_file):
        error_msg = f"{adp_file} 文件不存在，请先运行 fetch_adp_cached.py"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
        sys.exit(1)
    
    # 加载数据
    try:
        rankings_df = pd.read_csv(rankings_file)
        adp_df = pd.read_csv(adp_file)
        
        logger.info(f"成功加载数据:")
        logger.info(f"- 排名文件: {rankings_file}")
        logger.info(f"- 排名数据行数: {len(rankings_df)}")
        logger.info(f"- ADP数据行数: {len(adp_df)}")
        
        return rankings_df, adp_df
    except Exception as e:
        error_msg = f"加载数据时出错: {str(e)}"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
        sys.exit(1)


def find_sleepers(rankings_df, adp_df, min_adp=80, max_adp=300, min_bias=30, position=None, top=20):
    """
    寻找被低估的球员
    """
    logger.info(f"开始寻找Sleeper球员...")
    logger.info(f"参数设置:")
    logger.info(f"- 最小ADP: {min_adp}")
    logger.info(f"- 最大ADP: {max_adp}")
    logger.info(f"- 最小低估顺位: {min_bias}")
    logger.info(f"- 位置筛选: {position or '所有位置'}")
    logger.info(f"- 输出数量: {top}")
    
    # 合并数据，处理列名冲突
    merged_df = pd.merge(rankings_df, adp_df, on='name', how='inner', suffixes=('_rankings', '_adp'))
    logger.info(f"合并后数据行数: {len(merged_df)}")
    
    # 计算预期顺位（VORP排名）
    merged_df['expected_pick'] = merged_df['vorp'].rank(ascending=False).astype(int)
    
    # 计算低估程度
    merged_df['bias'] = merged_df['adp'] - merged_df['expected_pick']
    
    # 筛选条件
    filters = (merged_df['adp'] >= min_adp) & (merged_df['adp'] <= max_adp) & (merged_df['bias'] >= min_bias)
    
    if position:
        filters &= merged_df['pos_rankings'] == position
    
    # 应用筛选
    sleepers = merged_df[filters].copy()
    logger.info(f"筛选后找到 {len(sleepers)} 个符合条件的球员")
    
    # 排序
    sleepers = sleepers.sort_values('bias', ascending=False).head(top)
    logger.info(f"最终选择前 {len(sleepers)} 个球员")
    
    return sleepers


def generate_report(sleepers):
    """
    生成报告
    """
    logger.info("开始生成报告...")
    
    # 创建reports目录
    os.makedirs('reports', exist_ok=True)
    logger.info("创建reports目录成功")
    
    # 保存CSV
    output_file = 'reports/sleeper_recommendations.csv'
    try:
        sleepers.to_csv(output_file, index=False)
        logger.info(f"成功保存报告文件: {output_file}")
    except Exception as e:
        error_msg = f"保存报告文件时出错: {str(e)}"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
    
    # 打印结果
    print(f"🔥 Top {len(sleepers)} Sleeper Players (ADP {args.min_adp}-{args.max_adp})")
    print("========================================================================================================")
    
    for _, player in sleepers.iterrows():
        print(f"{player['name']:20} ({player['pos_rankings']}) | ADP: {player['adp']:4} → 应有: {player['expected_pick']:4} | VORP: {player['vorp']:6.1f} | 被低估 {player['bias']:3} 顺位")
    
    print(f"\n生成文件: {output_file}")
    logger.info(f"报告生成完成，共包含 {len(sleepers)} 个Sleeper球员")


def main(args):
    """
    主函数
    """
    logger.info("=========================================")
    logger.info("开始执行 Fantasy Baseball Sleeper 推荐器")
    logger.info("=========================================")
    
    # 加载数据
    rankings_df, adp_df = load_data()
    
    # 寻找sleepers
    sleepers = find_sleepers(
        rankings_df, adp_df,
        min_adp=args.min_adp,
        max_adp=args.max_adp,
        min_bias=args.min_bias,
        position=args.position,
        top=args.top
    )
    
    # 生成报告
    generate_report(sleepers)
    
    logger.info("=========================================")
    logger.info("Fantasy Baseball Sleeper 推荐器执行完成")
    logger.info("=========================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fantasy Baseball Sleeper 推荐器 v1.0')
    parser.add_argument('--min-adp', type=int, default=80, help='最小 ADP')
    parser.add_argument('--max-adp', type=int, default=300, help='最大 ADP')
    parser.add_argument('--min-bias', type=int, default=30, help='最小低估顺位')
    parser.add_argument('--position', type=str, help='仅分析特定位置')
    parser.add_argument('--top', type=int, default=20, help='输出前 N 名')
    
    args = parser.parse_args()
    main(args)
