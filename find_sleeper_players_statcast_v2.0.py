#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fantasy Baseball Sleeper 推荐器 v2.0
融合 Statcast 底层指标，挖掘“运气差”红利球员
"""

import os
import sys
import argparse
import pandas as pd

# 添加日志功能
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('find_sleeper_players_statcast')


def load_data():
    """
    加载必要的数据文件
    """
    logger.info("开始加载数据...")
    
    # 检查数据文件是否存在
    rankings_file = 'fantasy_draft_rankings_vorp_2026.csv'
    adp_file = 'adp.csv'
    batter_statcast_file = 'data/statcast_batter_2025.csv'
    pitcher_statcast_file = 'data/statcast_pitcher_2025.csv'
    
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
    
    if not (os.path.exists(batter_statcast_file) or os.path.exists(pitcher_statcast_file)):
        warning_msg = f"Statcast 数据文件不存在，请从 Baseball Savant 下载并保存至 data/ 目录"
        logger.warning(warning_msg)
        logger.warning(f"建议文件：{batter_statcast_file} 和 {pitcher_statcast_file}")
        print(f"警告：{warning_msg}")
        print(f"建议文件：{batter_statcast_file} 和 {pitcher_statcast_file}")
    
    # 加载基础数据
    try:
        rankings_df = pd.read_csv(rankings_file)
        adp_df = pd.read_csv(adp_file)
        
        logger.info(f"成功加载基础数据:")
        logger.info(f"- 排名文件: {rankings_file}")
        logger.info(f"- 排名数据行数: {len(rankings_df)}")
        logger.info(f"- ADP数据行数: {len(adp_df)}")
    except Exception as e:
        error_msg = f"加载基础数据时出错: {str(e)}"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
        sys.exit(1)
    
    # 加载Statcast数据
    statcast_batter_df = None
    statcast_pitcher_df = None
    
    if os.path.exists(batter_statcast_file):
        try:
            statcast_batter_df = pd.read_csv(batter_statcast_file)
            # 处理姓名格式
            statcast_batter_df['name'] = statcast_batter_df.apply(lambda x: f"{x['First Name']} {x['Last Name']}" if 'First Name' in x and 'Last Name' in x else x.get('name', ''), axis=1)
            logger.info(f"成功加载打者Statcast数据: {len(statcast_batter_df)} 行")
        except Exception as e:
            error_msg = f"加载打者Statcast数据时出错: {str(e)}"
            logger.error(error_msg)
            print(f"错误：{error_msg}")
    
    if os.path.exists(pitcher_statcast_file):
        try:
            statcast_pitcher_df = pd.read_csv(pitcher_statcast_file)
            # 处理姓名格式
            statcast_pitcher_df['name'] = statcast_pitcher_df.apply(lambda x: f"{x['First Name']} {x['Last Name']}" if 'First Name' in x and 'Last Name' in x else x.get('name', ''), axis=1)
            logger.info(f"成功加载投手Statcast数据: {len(statcast_pitcher_df)} 行")
        except Exception as e:
            error_msg = f"加载投手Statcast数据时出错: {str(e)}"
            logger.error(error_msg)
            print(f"错误：{error_msg}")
    
    return rankings_df, adp_df, statcast_batter_df, statcast_pitcher_df


def find_sleepers(rankings_df, adp_df, statcast_batter_df, statcast_pitcher_df, min_adp=80, max_adp=300, min_bias=30, position=None, top=15):
    """
    寻找被低估的球员（融合Statcast数据）
    """
    logger.info(f"开始寻找Sleeper球员（Statcast增强版）...")
    logger.info(f"参数设置:")
    logger.info(f"- 最小ADP: {min_adp}")
    logger.info(f"- 最大ADP: {max_adp}")
    logger.info(f"- 最小低估顺位: {min_bias}")
    logger.info(f"- 位置筛选: {position or '所有位置'}")
    logger.info(f"- 输出数量: {top}")
    
    # 合并基础数据，处理列名冲突
    merged_df = pd.merge(rankings_df, adp_df, on='name', how='inner', suffixes=('_rankings', '_adp'))
    logger.info(f"合并后数据行数: {len(merged_df)}")
    
    # 计算预期顺位（VORP排名）
    merged_df['expected_pick'] = merged_df['vorp'].rank(ascending=False).astype(int)
    
    # 计算低估程度
    merged_df['bias'] = merged_df['adp'] - merged_df['expected_pick']
    
    # 基础筛选条件
    filters = (merged_df['adp'] >= min_adp) & (merged_df['adp'] <= max_adp) & (merged_df['bias'] >= min_bias)
    
    if position:
        filters &= merged_df['pos_rankings'] == position
    
    # 应用基础筛选
    candidates = merged_df[filters].copy()
    logger.info(f"基础筛选后找到 {len(candidates)} 个符合条件的球员")
    
    # 添加Statcast信号
    candidates['statcast_signal'] = ''
    candidates['statcast_strength'] = 0
    
    # 处理打者
    if statcast_batter_df is not None:
        batter_count = 0
        for idx, player in candidates[candidates['pos_rankings'].isin(['C', '1B', '2B', '3B', 'SS', 'OF', 'UTIL'])].iterrows():
            statcast_player = statcast_batter_df[statcast_batter_df['name'] == player['name']]
            if not statcast_player.empty:
                batter = statcast_player.iloc[0]
                signals = []
                strength = 0
                
                # 检查xwOBA和AVG
                if 'xwOBA' in batter and 'AVG' in batter:
                    if batter['xwOBA'] >= 0.340 and batter['AVG'] < 0.250:
                        signals.append("xwOBA ≥.340 但 AVG <.250（运气差）")
                        strength += 2
                
                # 检查exit_velocity和barrel%
                if 'exit_velocity' in batter and 'barrel%' in batter:
                    if batter['exit_velocity'] >= 90 and batter['barrel%'] >= 8:
                        signals.append("高 EV + 高桶率（硬核打者）")
                        strength += 2
                elif 'Exit Velocity' in batter and 'Barrel %' in batter:
                    if batter['Exit Velocity'] >= 90 and batter['Barrel %'] >= 8:
                        signals.append("高 EV + 高桶率（硬核打者）")
                        strength += 2
                
                if signals:
                    candidates.at[idx, 'statcast_signal'] = '; '.join(signals)
                    candidates.at[idx, 'statcast_strength'] = strength
                    batter_count += 1
        logger.info(f"处理打者Statcast数据：发现 {batter_count} 个有信号的打者")
    
    # 处理投手
    if statcast_pitcher_df is not None:
        pitcher_count = 0
        for idx, player in candidates[candidates['pos_rankings'].isin(['SP', 'RP'])].iterrows():
            statcast_player = statcast_pitcher_df[statcast_pitcher_df['name'] == player['name']]
            if not statcast_player.empty:
                pitcher = statcast_player.iloc[0]
                signals = []
                strength = 0
                
                # 检查xERA和ERA
                if 'xERA' in pitcher and 'ERA' in pitcher:
                    if pitcher['xERA'] <= 3.5 and pitcher['ERA'] > 4.5:
                        signals.append("xERA ≤3.5 但 ERA >4.5（防御运气差）")
                        strength += 2
                
                # 检查whiff%和K%
                if 'whiff%' in pitcher and 'K%' in pitcher:
                    if pitcher['whiff%'] >= 30 and pitcher['K%'] >= 25:
                        signals.append("高挥空 + 高三振（压制力强）")
                        strength += 2
                elif 'Whiff %' in pitcher and 'K %' in pitcher:
                    if pitcher['Whiff %'] >= 30 and pitcher['K %'] >= 25:
                        signals.append("高挥空 + 高三振（压制力强）")
                        strength += 2
                
                if signals:
                    candidates.at[idx, 'statcast_signal'] = '; '.join(signals)
                    candidates.at[idx, 'statcast_strength'] = strength
                    pitcher_count += 1
        logger.info(f"处理投手Statcast数据：发现 {pitcher_count} 个有信号的投手")
    
    # 筛选具有Statcast信号的球员
    statcast_candidates = candidates[candidates['statcast_strength'] > 0]
    logger.info(f"Statcast信号筛选后找到 {len(statcast_candidates)} 个球员")
    
    # 如果没有Statcast数据或没有符合条件的球员，返回基础筛选结果
    if statcast_candidates.empty:
        warning_msg = "没有找到符合Statcast条件的球员，返回基础筛选结果"
        logger.warning(warning_msg)
        print(f"警告：{warning_msg}")
        sleepers = candidates.sort_values('bias', ascending=False).head(top)
        logger.info(f"返回基础筛选结果：{len(sleepers)} 个球员")
    else:
        # 按Statcast强度和低估程度排序
        sleepers = statcast_candidates.sort_values(['statcast_strength', 'bias'], ascending=False).head(top)
        logger.info(f"返回Statcast增强结果：{len(sleepers)} 个球员")
    
    return sleepers


def generate_report(sleepers):
    """
    生成报告
    """
    logger.info("开始生成Statcast增强版报告...")
    
    # 创建reports目录
    os.makedirs('reports', exist_ok=True)
    logger.info("创建reports目录成功")
    
    # 保存CSV
    output_file = 'reports/sleeper_statcast_v2.0.csv'
    try:
        sleepers.to_csv(output_file, index=False)
        logger.info(f"成功保存报告文件: {output_file}")
    except Exception as e:
        error_msg = f"保存报告文件时出错: {str(e)}"
        logger.error(error_msg)
        print(f"错误：{error_msg}")
    
    # 打印结果
    print(f"🔥 Top {len(sleepers)} Statcast Sleeper v2.0 (ADP {args.min_adp}-{args.max_adp})")
    print("========================================================================================================")
    
    for _, player in sleepers.iterrows():
        signal_text = f" | Statcast 优势: {player['statcast_signal']}" if player['statcast_signal'] else ""
        print(f"{player['name']:20} ({player['pos_rankings']}) | ADP: {player['adp']:4} → 应有: {player['expected_pick']:4} | VORP: {player['vorp']:6.1f} | 被低估 {player['bias']:3} 顺位{signal_text}")
    
    print(f"\n生成文件: {output_file}")
    logger.info(f"Statcast增强版报告生成完成，共包含 {len(sleepers)} 个Sleeper球员")


def main(args):
    """
    主函数
    """
    logger.info("=========================================")
    logger.info("开始执行 Fantasy Baseball Sleeper 推荐器 v2.0")
    logger.info("=========================================")
    
    # 加载数据
    rankings_df, adp_df, statcast_batter_df, statcast_pitcher_df = load_data()
    
    # 寻找sleepers
    sleepers = find_sleepers(
        rankings_df, adp_df, statcast_batter_df, statcast_pitcher_df,
        min_adp=args.min_adp,
        max_adp=args.max_adp,
        min_bias=args.min_bias,
        position=args.position,
        top=args.top
    )
    
    # 生成报告
    generate_report(sleepers)
    
    logger.info("=========================================")
    logger.info("Fantasy Baseball Sleeper 推荐器 v2.0 执行完成")
    logger.info("=========================================")


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description='Fantasy Baseball Sleeper 推荐器 v2.0')
    parser.add_argument('--min-adp', type=int, default=80, help='最小 ADP')
    parser.add_argument('--max-adp', type=int, default=300, help='最大 ADP')
    parser.add_argument('--min-bias', type=int, default=30, help='最小低估顺位或Statcast信号强度')
    parser.add_argument('--position', type=str, help='仅分析特定位置')
    parser.add_argument('--top', type=int, default=15, help='输出前 N 名')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
