#!/usr/bin/env python3
import argparse
import yaml
import pandas as pd
import json
import os
from datetime import datetime
from .draft_engine import DraftEngine
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import ConfigLoader
from fetch_adp_cached import ADPFetcher

# 添加日志功能
from utils.logger import get_logger
logger = get_logger('draft_simulator')

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='动态选秀模拟器')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='配置文件路径')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='模拟次数')
    parser.add_argument('--output', type=str, default='simulation_results',
                        help='输出目录')
    parser.add_argument('--target-pick', type=int, default=None,
                        help='目标选秀位置（用于可用性分析）')
    parser.add_argument('--report-only', action='store_true',
                        help='仅生成报告，不运行模拟')
    return parser.parse_args()

def load_data(config):
    """加载球员数据和 ADP 数据"""
    # 加载 ADP 数据
    adp_fetcher = ADPFetcher()
    adp_data = adp_fetcher.fetch_adp()
    
    # 模拟球员数据
    player_pool = _mock_player_data()
    
    return player_pool, adp_data

def _mock_player_data():
    """模拟球员数据"""
    import pandas as pd
    import numpy as np
    
    # 模拟打者数据
    hitters_data = {
        'player_id': list(range(1, 101)),
        'player_name': [f'Player H{i}' for i in range(1, 101)],
        'position': list(np.random.choice(['C', '1B', '2B', '3B', 'SS', 'OF'], 100)),
        'vorp': list(np.random.normal(50, 20, 100)),
        'fantasy_points': list(np.random.normal(100, 30, 100)),
        'replacement_level': [30] * 100,
        'risk_score': list(np.random.uniform(0, 1, 100)),
        'age': list(np.random.randint(20, 40, 100))
    }
    hitters = pd.DataFrame(hitters_data)
    
    # 模拟投手数据
    pitchers_data = {
        'player_id': list(range(101, 201)),
        'player_name': [f'Player P{i}' for i in range(1, 101)],
        'position': list(np.random.choice(['SP', 'RP'], 100)),
        'vorp': list(np.random.normal(40, 15, 100)),
        'fantasy_points': list(np.random.normal(90, 25, 100)),
        'replacement_level': [25] * 100,
        'risk_score': list(np.random.uniform(0, 1, 100)),
        'age': list(np.random.randint(20, 40, 100))
    }
    pitchers = pd.DataFrame(pitchers_data)
    
    # 合并数据
    player_pool = pd.concat([hitters, pitchers], ignore_index=True)
    
    return player_pool

def run_simulation(args):
    """运行选秀模拟"""
    logger.info("=========================================")
    logger.info("开始执行动态选秀模拟")
    logger.info("=========================================")
    
    # 加载配置
    logger.info(f"加载配置文件: {args.config}")
    config_loader = ConfigLoader(args.config)
    config = config_loader.load()
    logger.info("配置加载成功")
    
    # 加载数据
    logger.info("开始加载数据...")
    print("加载数据...")
    player_pool, adp_data = load_data(config)
    logger.info(f"数据加载完成: {len(player_pool)} 个球员, {len(adp_data)} 条ADP记录")
    
    # 初始化选秀引擎
    logger.info("初始化选秀引擎...")
    print("初始化选秀引擎...")
    engine = DraftEngine(config, player_pool, adp_data)
    logger.info("选秀引擎初始化成功")
    
    # 如果指定了目标选秀位置，进行可用性分析
    if args.target_pick:
        logger.info(f"分析选秀位置 {args.target_pick} 的球员可用性...")
        print(f"分析选秀位置 {args.target_pick} 的球员可用性...")
        availability = engine.analyze_player_availability(args.target_pick)
        
        # 保存可用性分析结果
        output_dir = args.output
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"创建输出目录: {output_dir}")
        
        availability_file = os.path.join(output_dir, f'availability_pick_{args.target_pick}.csv')
        availability.to_csv(availability_file, index=False)
        logger.info(f"可用性分析结果已保存到: {availability_file}")
        print(f"可用性分析结果已保存到: {availability_file}")
        
        # 显示前 20 个最有可能可用的球员
        logger.info("显示前 20 个最有可能可用的球员")
        print("\n前 20 个最有可能可用的球员:")
        top_available = availability.nlargest(20, ['availability_prob', 'vorp'])
        print(top_available[["player_name", "position", "vorp", "adp", "availability_prob"]])
    
    # 如果不是仅生成报告模式，运行模拟
    if not args.report_only:
        logger.info(f"开始运行 {args.iterations} 次模拟...")
        print(f"开始运行 {args.iterations} 次模拟...")
        results = engine.simulate_draft(iterations=args.iterations)
        logger.info(f"模拟完成，共运行 {args.iterations} 次")
        
        # 生成模拟报告
        logger.info("生成模拟报告...")
        print("生成模拟报告...")
        report = engine.generate_simulation_report(results)
        logger.info("模拟报告生成成功")
        
        # 保存结果
        logger.info(f"保存结果到目录: {args.output}")
        save_results(results, report, args.output)
        
        # 显示摘要
        logger.info("显示模拟结果摘要")
        display_summary(report)
    
    logger.info("模拟完成！")
    logger.info("=========================================")
    logger.info("动态选秀模拟执行完成")
    logger.info("=========================================")
    print("模拟完成！")

def save_results(results, report, output_dir):
    """保存模拟结果"""
    logger.info(f"开始保存结果到目录: {output_dir}")
    
    os.makedirs(output_dir, exist_ok=True)
    logger.info("创建输出目录成功")
    
    # 保存球员分析结果
    player_analysis_file = os.path.join(output_dir, 'player_analysis.csv')
    report['player_analysis'].to_csv(player_analysis_file, index=False)
    logger.info(f"保存球员分析结果: {player_analysis_file}")
    
    # 保存策略分析结果
    strategy_analysis_file = os.path.join(output_dir, 'strategy_analysis.csv')
    report['strategy_analysis'].to_csv(strategy_analysis_file, index=False)
    logger.info(f"保存策略分析结果: {strategy_analysis_file}")
    
    # 保存模拟结果（前 100 次）
    sample_results = results[:100]  # 只保存前 100 次模拟结果
    results_file = os.path.join(output_dir, 'sample_simulation_results.json')
    
    # 转换为可序列化的格式
    def convert_to_serializable(obj):
        """将对象转换为可序列化的类型"""
        if isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_serializable(item) for item in obj]
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    serializable_results = []
    for result in sample_results:
        serializable_result = {
            'draft_picks': convert_to_serializable(result['draft_picks']),
            'team_values': convert_to_serializable(result['team_values'])
        }
        serializable_results.append(serializable_result)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)
    logger.info(f"保存模拟结果: {results_file}")
    
    # 保存模拟摘要
    summary_file = os.path.join(output_dir, 'simulation_summary.txt')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"模拟摘要\n")
        f.write(f"模拟次数: {report['total_simulations']}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n策略分析:\n")
        for _, row in report['strategy_analysis'].iterrows():
            f.write(f"{row['strategy']}: 平均 VORP = {row['vorp']:.2f}, 平均选秀位置 = {row['pick_number']:.2f}\n")
        
        f.write("\n前 10 名价值最高的球员:\n")
        top_players = report['player_analysis'].nlargest(10, 'value_per_pick')
        for _, row in top_players.iterrows():
            f.write(f"{row['player_name']} ({row['position']}): 价值/选秀位置 = {row['value_per_pick']:.2f}, 平均选秀位置 = {row['avg_pick']:.2f}\n")
    logger.info(f"保存模拟摘要: {summary_file}")
    
    print(f"结果已保存到目录: {output_dir}")
    logger.info("所有结果保存完成")

def display_summary(report):
    """显示模拟结果摘要"""
    print("\n=== 模拟结果摘要 ===")
    print(f"模拟次数: {report['total_simulations']}")
    
    print("\n策略分析:")
    for _, row in report['strategy_analysis'].iterrows():
        print(f"{row['strategy']}: 平均 VORP = {row['vorp']:.2f}, 平均选秀位置 = {row['pick_number']:.2f}")
    
    print("\n前 10 名价值最高的球员:")
    top_players = report['player_analysis'].nlargest(10, 'value_per_pick')
    for _, row in top_players.iterrows():
        print(f"{row['player_name']} ({row['position']}): 价值/选秀位置 = {row['value_per_pick']:.2f}, 平均选秀位置 = {row['avg_pick']:.2f}")
    
    print("\n前 10 名被选中次数最多的球员:")
    most_drafted = report['player_analysis'].nlargest(10, 'times_drafted')
    for _, row in most_drafted.iterrows():
        print(f"{row['player_name']} ({row['position']}): {row['times_drafted']} 次")

def main():
    """主函数"""
    args = parse_args()
    run_simulation(args)

if __name__ == '__main__':
    main()