#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选秀模拟器工具
负责模拟蛇形选秀过程，提供价值股提示和策略建议
"""

import os
import sqlite3
import pandas as pd
import argparse
from typing import Dict, List, Optional, Tuple
from config_loader import get_config


class SnakeDraftSimulator:
    """蛇形选秀模拟器类"""
    
    def __init__(self, db_path: str = 'fantasy_baseball.db'):
        """
        初始化选秀模拟器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.config = get_config()
        self.conn = None
        self.cursor = None
        self.rankings = None
        self.adp_data = None
        self.draft_order = []
        self.drafted_players = set()
        self.team_rosters = {}
        self.rounds = self.config['league']['rounds']
        self.league_size = self.config['league']['size']
        self.roster_slots = self.config['league']['roster_slots']
        self.default_strategy = self.config['draft_simulator']['default_strategy']
        self.show_value_picks = self.config['draft_simulator']['show_value_picks']
    
    def connect_db(self) -> None:
        """
        连接到SQLite数据库
        """
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def disconnect_db(self) -> None:
        """
        断开数据库连接
        """
        if self.conn:
            self.conn.close()
    
    def load_rankings(self) -> None:
        """
        加载球员排名数据
        """
        # 尝试从CSV文件加载排名
        rankings_file = 'fantasy_draft_rankings_vorp_2026.csv'
        if os.path.exists(rankings_file):
            self.rankings = pd.read_csv(rankings_file)
        else:
            # 如果CSV文件不存在，从数据库计算
            from fantasy_scoring_model_v2 import FantasyScoringModel
            model = FantasyScoringModel(self.db_path)
            model.connect_db()
            self.rankings = model.calculate_vorp()
            model.disconnect_db()
        
        # 确保排名数据有效
        if self.rankings is None or self.rankings.empty:
            raise ValueError("无法加载球员排名数据")
    
    def load_adp(self) -> None:
        """
        加载ADP（平均选秀位置）数据
        """
        adp_file = self.config['draft_simulator']['adp_file']
        if os.path.exists(adp_file):
            try:
                self.adp_data = pd.read_csv(adp_file)
                print(f"✅ 成功加载ADP数据: {adp_file}")
            except Exception as e:
                print(f"⚠️ 加载ADP数据失败: {e}")
                self.adp_data = None
        else:
            print(f"⚠️ ADP文件不存在: {adp_file}")
            self.adp_data = None
    
    def generate_draft_order(self, user_pick: int = 1) -> None:
        """
        生成选秀顺序
        
        Args:
            user_pick: 用户的选秀顺位（1-联盟规模）
        """
        if user_pick < 1 or user_pick > self.league_size:
            raise ValueError(f"选秀顺位必须在1-{self.league_size}之间")
        
        # 生成标准蛇形选秀顺序
        for round_num in range(1, self.rounds + 1):
            round_order = []
            if round_num % 2 == 1:
                # 奇数轮：1, 2, 3, ..., league_size
                round_order = list(range(1, self.league_size + 1))
            else:
                # 偶数轮：league_size, league_size-1, ..., 1
                round_order = list(range(self.league_size, 0, -1))
            
            self.draft_order.append(round_order)
        
        # 初始化球队阵容
        for team_id in range(1, self.league_size + 1):
            self.team_rosters[team_id] = {
                'picks': [],
                'roster': {}
            }
        
        print(f"✅ 生成了 {self.rounds} 轮选秀顺序")
        print(f"🎯 你的选秀顺位: 第 {user_pick} 位")
    
    def simulate_draft(self, user_pick: int = 1, strategy: Optional[str] = None) -> None:
        """
        模拟选秀过程
        
        Args:
            user_pick: 用户的选秀顺位
            strategy: 选秀策略 (conservative/balanced/aggressive)
        """
        # 加载数据
        self.load_rankings()
        self.load_adp()
        
        # 生成选秀顺序
        self.generate_draft_order(user_pick)
        
        # 使用指定策略或默认策略
        if strategy is None:
            strategy = self.default_strategy
        
        print(f"\n=== 开始模拟选秀 (策略: {strategy}) ===")
        
        # 模拟每一轮选秀
        for round_num, round_order in enumerate(self.draft_order, 1):
            print(f"\n--- 第 {round_num} 轮 ---\n")
            
            # 每一轮的选秀
            for pick_num, team_id in enumerate(round_order, 1):
                # 计算总选秀位置
                total_pick = (round_num - 1) * self.league_size + pick_num
                
                # 选择球员
                selected_player = self._select_player(team_id, round_num, pick_num, total_pick, strategy)
                
                if selected_player is not None:
                    # 记录选秀结果
                    self._record_pick(team_id, round_num, pick_num, selected_player)
                    
                    # 标记球员为已选中
                    self.drafted_players.add(selected_player['name'])
                    
                    # 显示选秀结果
                    self._display_pick(team_id, round_num, pick_num, selected_player, user_pick)
        
        # 显示最终阵容
        self._display_final_roster(user_pick)
        
        # 保存选秀日志
        self._save_draft_log(user_pick, strategy)
    
    def _select_player(self, team_id: int, round_num: int, pick_num: int, total_pick: int, strategy: str) -> Optional[Dict]:
        """
        为指定球队选择球员
        
        Args:
            team_id: 球队ID
            round_num: 轮数
            pick_num: 本轮选秀顺位
            total_pick: 总选秀位置
            strategy: 选秀策略
            
        Returns:
            选中的球员信息
        """
        # 过滤出未被选中的球员
        available_players = self.rankings[~self.rankings['name'].isin(self.drafted_players)]
        
        if available_players.empty:
            return None
        
        # 根据策略选择球员
        if strategy == 'aggressive':
            # 激进策略：优先选择vorp_upside高的球员
            available_players = available_players.sort_values('vorp_upside', ascending=False)
        elif strategy == 'conservative':
            # 保守策略：优先选择vorp_floor高的球员
            available_players = available_players.sort_values('vorp_floor', ascending=False)
        else:
            # 平衡策略：优先选择vorp高的球员
            available_players = available_players.sort_values('vorp', ascending=False)
        
        # 简单的阵容需求考虑
        team_roster = self.team_rosters[team_id]['roster']
        
        # 计算当前阵容各位置的数量
        pos_counts = {pos: 0 for pos in self.roster_slots.keys()}
        for player in team_roster.values():
            if 'pos' in player:
                pos = player['pos']
                if pos in pos_counts:
                    pos_counts[pos] += 1
        
        # 优先选择阵容中缺少的位置
        best_player = None
        best_score = -float('inf')
        
        for _, player in available_players.iterrows():
            pos = player['pos']
            
            # 检查位置是否已满
            if pos_counts.get(pos, 0) >= self.roster_slots.get(pos, 0):
                # 位置已满，只有UTIL位置可以考虑
                if pos not in ['UTIL']:
                    continue
            
            # 计算球员评分
            if strategy == 'aggressive':
                score = player.get('vorp_upside', 0)
            elif strategy == 'conservative':
                score = player.get('vorp_floor', 0)
            else:
                score = player.get('vorp', 0)
            
            # 位置稀缺性调整
            if pos_counts.get(pos, 0) < self.roster_slots.get(pos, 0):
                score *= 1.1  # 对需要的位置给予10%的加成
            
            if score > best_score:
                best_score = score
                best_player = player.to_dict()
        
        # 如果没有找到合适的球员，就选择评分最高的
        if best_player is None and not available_players.empty:
            best_player = available_players.iloc[0].to_dict()
        
        return best_player
    
    def _record_pick(self, team_id: int, round_num: int, pick_num: int, player: Dict) -> None:
        """
        记录选秀结果
        
        Args:
            team_id: 球队ID
            round_num: 轮数
            pick_num: 本轮选秀顺位
            player: 选中的球员信息
        """
        # 记录选秀
        pick_info = {
            'round': round_num,
            'pick': pick_num,
            'name': player['name'],
            'pos': player['pos'],
            'vorp': player.get('vorp', 0),
            'vorp_upside': player.get('vorp_upside', 0),
            'vorp_floor': player.get('vorp_floor', 0)
        }
        
        self.team_rosters[team_id]['picks'].append(pick_info)
        
        # 记录到阵容
        pos = player['pos']
        if pos not in self.team_rosters[team_id]['roster']:
            self.team_rosters[team_id]['roster'][pos] = []
        
        self.team_rosters[team_id]['roster'][pos].append(player)
    
    def _display_pick(self, team_id: int, round_num: int, pick_num: int, player: Dict, user_pick: int) -> None:
        """
        显示选秀结果
        
        Args:
            team_id: 球队ID
            round_num: 轮数
            pick_num: 本轮选秀顺位
            player: 选中的球员信息
            user_pick: 用户的选秀顺位
        """
        # 计算总选秀位置
        total_pick = (round_num - 1) * self.league_size + pick_num
        
        # 构建显示文本
        is_user_pick = (team_id == user_pick)
        pick_prefix = "🎯" if is_user_pick else "📋"
        team_label = f"你" if is_user_pick else f"球队 {team_id}"
        
        # 检查是否是价值股
        is_value_pick = False
        value_diff = 0
        
        if self.show_value_picks and self.adp_data is not None:
            # 简单的价值股判断：当前选秀位置低于ADP
            player_adp = self.adp_data[self.adp_data['name'] == player['name']]['adp'].values
            if len(player_adp) > 0:
                value_diff = player_adp[0] - total_pick
                if value_diff > 5:  # 价值差异大于5个位置
                    is_value_pick = True
        
        # 显示选秀结果
        print(f"{pick_prefix} 第 {round_num} 轮第 {pick_num} 顺位 - {team_label} 选择:")
        print(f"   👤 {player['name']} ({player['pos']})")
        print(f"   📊 VORP: {player.get('vorp', 0):.2f} | 上限: {player.get('vorp_upside', 0):.2f} | 下限: {player.get('vorp_floor', 0):.2f}")
        
        if is_value_pick:
            print(f"   💎 价值股! ADP差异: +{value_diff}")
        
        print()
    
    def _display_final_roster(self, user_pick: int) -> None:
        """
        显示最终阵容
        
        Args:
            user_pick: 用户的选秀顺位
        """
        print("\n=== 最终阵容 ===\n")
        
        user_roster = self.team_rosters.get(user_pick, {})
        picks = user_roster.get('picks', [])
        roster = user_roster.get('roster', {})
        
        print("你的选秀结果:")
        print("-" * 80)
        
        # 按轮次显示选秀
        for pick_info in picks:
            round_num = pick_info['round']
            pick_num = pick_info['pick']
            name = pick_info['name']
            pos = pick_info['pos']
            vorp = pick_info['vorp']
            
            print(f"第 {round_num} 轮第 {pick_num} 顺位: {name} ({pos}) - VORP: {vorp:.2f}")
        
        print("-" * 80)
        print("你的最终阵容:")
        print("-" * 80)
        
        # 显示各位置球员
        for pos, players in roster.items():
            if players:
                print(f"{pos}: {len(players)}/{self.roster_slots.get(pos, 0)}")
                for player in players:
                    print(f"   - {player['name']}")
        
        print("-" * 80)
    
    def _save_draft_log(self, user_pick: int, strategy: str) -> None:
        """
        保存选秀日志
        
        Args:
            user_pick: 用户的选秀顺位
            strategy: 选秀策略
        """
        log_file = f"draft_log_pick{user_pick}_{strategy}.csv"
        
        # 准备日志数据
        log_data = []
        user_roster = self.team_rosters.get(user_pick, {})
        picks = user_roster.get('picks', [])
        
        for pick_info in picks:
            log_entry = {
                'round': pick_info['round'],
                'pick': pick_info['pick'],
                'name': pick_info['name'],
                'pos': pick_info['pos'],
                'vorp': pick_info['vorp'],
                'vorp_upside': pick_info['vorp_upside'],
                'vorp_floor': pick_info['vorp_floor']
            }
            log_data.append(log_entry)
        
        # 保存到CSV
        if log_data:
            log_df = pd.DataFrame(log_data)
            log_df.to_csv(log_file, index=False)
            print(f"\n✅ 成功保存选秀日志: {log_file}")


def main():
    """
    主函数
    """
    print("=== Fantasy Baseball 选秀模拟器 ===")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Fantasy Baseball 蛇形选秀模拟器')
    parser.add_argument('--pick', type=int, default=1, help='你的选秀顺位 (1-12)')
    parser.add_argument('--strategy', type=str, default=None, help='选秀策略 (conservative/balanced/aggressive)')
    args = parser.parse_args()
    
    # 创建选秀模拟器
    simulator = SnakeDraftSimulator()
    
    try:
        # 连接数据库
        simulator.connect_db()
        
        # 加载数据
        simulator.load_rankings()
        simulator.load_adp()
        
        # 模拟选秀
        simulator.simulate_draft(args.pick, args.strategy)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    finally:
        # 断开数据库连接
        simulator.disconnect_db()


if __name__ == '__main__':
    main()
