#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阵容验证工具
负责验证选秀后阵容的合规性，避免超编问题
"""

import os
import argparse
import pandas as pd
from typing import Dict, List, Optional
from config_loader import get_config


class RosterValidator:
    """阵容验证器类"""
    
    def __init__(self):
        """
        初始化阵容验证器
        """
        self.config = get_config()
        self.roster_slots = self.config['league']['roster_slots']
    
    def validate_roster(self, draft_log_file: str) -> bool:
        """
        验证阵容合规性
        
        Args:
            draft_log_file: 选秀日志文件路径
            
        Returns:
            阵容是否合规
        """
        if not os.path.exists(draft_log_file):
            print(f"❌ 选秀日志文件不存在: {draft_log_file}")
            return False
        
        try:
            # 读取选秀日志
            draft_log = pd.read_csv(draft_log_file)
            print(f"✅ 读取选秀日志: {draft_log_file}")
            print(f"📊 共选择 {len(draft_log)} 名球员")
            
        except Exception as e:
            print(f"❌ 读取选秀日志失败: {e}")
            return False
        
        # 计算各位置球员数量
        pos_counts = {}
        for _, pick in draft_log.iterrows():
            pos = pick['pos']
            if pos not in pos_counts:
                pos_counts[pos] = 0
            pos_counts[pos] += 1
        
        # 验证各位置数量
        print("\n📋 阵容合规性检查:")
        print("-" * 80)
        
        is_valid = True
        suggestions = []
        
        for pos, max_count in self.roster_slots.items():
            current_count = pos_counts.get(pos, 0)
            
            if current_count == max_count:
                print(f"✅ {pos}: {current_count}/{max_count}")
            elif current_count < max_count:
                print(f"⚠️ {pos}: {current_count}/{max_count} → 缺少 {max_count - current_count} 个")
                is_valid = False
                suggestions.append(f"建议选择 {max_count - current_count} 个 {pos} 位置的球员")
            else:
                print(f"❌ {pos}: {current_count}/{max_count} → 超出 {current_count - max_count} 个")
                is_valid = False
                suggestions.append(f"建议减少 {current_count - max_count} 个 {pos} 位置的球员")
        
        # 检查是否有未使用的UTIL位置
        util_max = self.roster_slots.get('UTIL', 0)
        util_current = pos_counts.get('UTIL', 0)
        
        if util_max > 0 and util_current < util_max:
            # 查找可以移动到UTIL的球员
            movable_players = []
            for _, pick in draft_log.iterrows():
                pos = pick['pos']
                if pos != 'UTIL' and pos_counts.get(pos, 0) > self.roster_slots.get(pos, 0):
                    movable_players.append(pick['name'])
            
            if movable_players:
                suggestions.append(f"建议将 {movable_players[0]} 移至 UTIL 位置")
        
        print("-" * 80)
        
        # 显示建议
        if suggestions:
            print("\n💡 建议:")
            for suggestion in suggestions:
                print(f"   - {suggestion}")
        
        # 显示最终结果
        if is_valid:
            print("\n🎉 阵容完整且合规！")
        else:
            print("\n❗ 阵容不完整，请调整！")
        
        return is_valid
    
    def analyze_roster_strength(self, draft_log_file: str) -> None:
        """
        分析阵容强度
        
        Args:
            draft_log_file: 选秀日志文件路径
        """
        if not os.path.exists(draft_log_file):
            print(f"❌ 选秀日志文件不存在: {draft_log_file}")
            return
        
        try:
            # 读取选秀日志
            draft_log = pd.read_csv(draft_log_file)
            
        except Exception as e:
            print(f"❌ 读取选秀日志失败: {e}")
            return
        
        # 计算总VORP
        total_vorp = draft_log['vorp'].sum()
        avg_vorp = draft_log['vorp'].mean()
        
        # 计算打者和投手的VORP
        hitters_vorp = 0
        pitchers_vorp = 0
        
        for _, pick in draft_log.iterrows():
            # 简单判断球员类型
            pos = pick['pos']
            if pos in ['C', '1B', '2B', '3B', 'SS', 'OF', 'UTIL']:
                hitters_vorp += pick['vorp']
            elif pos in ['SP', 'RP']:
                pitchers_vorp += pick['vorp']
        
        # 分析各轮次选秀质量
        round_quality = []
        for round_num in sorted(draft_log['round'].unique()):
            round_picks = draft_log[draft_log['round'] == round_num]
            round_vorp = round_picks['vorp'].sum()
            round_avg_vorp = round_picks['vorp'].mean()
            round_quality.append((round_num, round_vorp, round_avg_vorp))
        
        print("\n=== 阵容强度分析 ===")
        print("-" * 80)
        print(f"总 VORP: {total_vorp:.2f}")
        print(f"平均 VORP: {avg_vorp:.2f}")
        print(f"打者总 VORP: {hitters_vorp:.2f}")
        print(f"投手总 VORP: {pitchers_vorp:.2f}")
        print(f"打者/投手 VORP 比例: {hitters_vorp/pitchers_vorp:.2f} : 1")
        print("-" * 80)
        
        print("\n各轮次选秀质量:")
        for round_num, round_vorp, round_avg_vorp in sorted(round_quality):
            print(f"第 {round_num} 轮: 总 VORP = {round_vorp:.2f}, 平均 VORP = {round_avg_vorp:.2f}")
        
        # 找出最佳和最差选秀
        best_pick = draft_log.loc[draft_log['vorp'].idxmax()]
        worst_pick = draft_log.loc[draft_log['vorp'].idxmin()]
        
        print("\n-" * 80)
        print(f"🏆 最佳选秀: {best_pick['name']} (第 {best_pick['round']} 轮) - VORP: {best_pick['vorp']:.2f}")
        print(f"📉 最差选秀: {worst_pick['name']} (第 {worst_pick['round']} 轮) - VORP: {worst_pick['vorp']:.2f}")
        print("-" * 80)


def main():
    """
    主函数
    """
    print("=== Fantasy Baseball 阵容验证工具 ===")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Fantasy Baseball 阵容验证工具')
    parser.add_argument('draft_log_file', help='选秀日志文件路径')
    parser.add_argument('--analyze', action='store_true', help='分析阵容强度')
    args = parser.parse_args()
    
    # 创建阵容验证器
    validator = RosterValidator()
    
    # 验证阵容
    is_valid = validator.validate_roster(args.draft_log_file)
    
    # 分析阵容强度
    if args.analyze:
        validator.analyze_roster_strength(args.draft_log_file)


if __name__ == '__main__':
    main()
