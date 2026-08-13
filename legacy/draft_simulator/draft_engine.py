import numpy as np
from numba import njit, prange
import pandas as pd
import json
import os
from datetime import datetime
from .ai_strategies import get_drafter

class DraftEngine:
    def __init__(self, config, player_pool, adp_data):
        self.config = config
        self.player_pool = player_pool
        self.adp_data = adp_data
        self.league_size = config['league']['size']
        self.rounds = config['league']['rounds']
        self.roster_slots = config['league']['roster_slots']
        self.strategies = config.get('draft_strategies', {
            'balanced': 0.2,
            'positional_hoarder': 0.2,
            'statcast_believer': 0.2,
            'adp_follower': 0.2,
            'your_strategy': 0.2
        })
        
        # 准备球员数据
        self.players_df = self._prepare_player_data()
        self.total_picks = self.league_size * self.rounds
        
    def _prepare_player_data(self):
        """准备球员数据，添加必要的字段"""
        df = self.player_pool.copy()
        
        # 添加 ADP 数据
        if 'adp' not in df.columns:
            # 检查 ADP 数据的列名
            if 'player_id' in self.adp_data.columns:
                # 使用 player_id 匹配
                df['adp'] = df['player_id'].map(self.adp_data.set_index('player_id')['adp']).fillna(999)
            else:
                # 使用球员名称匹配（如果可用）
                if 'name' in self.adp_data.columns and 'player_name' in df.columns:
                    df['adp'] = df['player_name'].map(self.adp_data.set_index('name')['adp']).fillna(999)
                else:
                    # 如果无法匹配，设置默认值
                    df['adp'] = 999
        
        # 添加风险评分
        if 'risk_score' not in df.columns:
            df['risk_score'] = 0.5  # 默认风险评分
        
        # 计算 VORP（如果不存在）
        if 'vorp' not in df.columns:
            df['vorp'] = df['fantasy_points'] - df['replacement_level']
        
        return df
    
    def simulate_draft(self, iterations=1000):
        """运行多次选秀模拟"""
        results = []
        
        for i in range(iterations):
            if (i + 1) % 100 == 0:
                print(f"完成模拟 {i + 1}/{iterations}")
            
            draft_result = self._run_single_simulation()
            results.append(draft_result)
        
        return results
    
    def _run_single_simulation(self):
        """运行单次选秀模拟"""
        # 初始化球队和选秀顺序
        teams = {i: {'roster': [], 'strategy': self._assign_strategy()} for i in range(self.league_size)}
        draft_order = self._generate_draft_order()
        
        # 跟踪可用球员
        available_players = self.players_df.copy()
        available_players['available'] = True
        
        # 选秀结果
        draft_picks = []
        
        # 开始选秀
        for pick_num in range(self.total_picks):
            team_idx = draft_order[pick_num]
            team = teams[team_idx]
            
            # 使用 AI 策略选择球员
            selected_player = self._select_player(team, available_players, pick_num)
            
            if selected_player is not None:
                # 更新球队阵容
                team['roster'].append(selected_player)
                
                # 标记球员为已选中
                available_players.loc[available_players['player_id'] == selected_player['player_id'], 'available'] = False
                
                # 记录选秀结果
                draft_picks.append({
                    'pick_number': pick_num + 1,
                    'team': team_idx + 1,
                    'player_id': selected_player['player_id'],
                    'player_name': selected_player['player_name'],
                    'position': selected_player['position'],
                    'vorp': selected_player['vorp'],
                    'adp': selected_player['adp'],
                    'strategy': team['strategy']
                })
        
        # 计算球队价值
        team_values = {}
        for team_idx, team in teams.items():
            team_values[team_idx + 1] = self._calculate_team_value(team['roster'])
        
        return {
            'draft_picks': draft_picks,
            'team_values': team_values
        }
    
    def _assign_strategy(self):
        """为球队分配选秀策略"""
        strategies = list(self.strategies.keys())
        weights = list(self.strategies.values())
        return np.random.choice(strategies, p=weights)
    
    def _generate_draft_order(self):
        """生成蛇形选秀顺序"""
        draft_order = []
        
        for round_num in range(self.rounds):
            if round_num % 2 == 0:
                # 偶数轮（从 0 开始）：正向
                draft_order.extend(range(self.league_size))
            else:
                # 奇数轮：反向
                draft_order.extend(reversed(range(self.league_size)))
        
        return draft_order
    
    def _select_player(self, team, available_players, pick_num):
        """根据策略选择球员"""
        # 获取可用球员
        available = available_players[available_players['available']].copy()
        
        if available.empty:
            return None
        
        # 获取当前球队的策略
        strategy_name = team['strategy']
        drafter = get_drafter(strategy_name, self.config)
        
        # 计算每个球员的价值
        available['value'] = drafter.calculate_value(
            available, 
            team['roster'], 
            self.roster_slots,
            pick_num,
            self.total_picks
        )
        
        # 选择价值最高的球员
        selected = available.nlargest(1, 'value').iloc[0]
        
        return selected.to_dict()
    
    def _calculate_team_value(self, roster):
        """计算球队总价值"""
        if not roster:
            return 0
        
        total_value = sum(player['vorp'] for player in roster)
        return total_value
    
    def analyze_player_availability(self, target_pick):
        """分析球员在目标选秀位置的可用性"""
        # 计算每个球员的可用概率
        players = self.players_df.copy()
        
        # 基于 ADP 计算可用性概率
        players['availability_prob'] = self._calculate_availability_prob(players['adp'], target_pick)
        
        return players[['player_id', 'player_name', 'position', 'vorp', 'adp', 'availability_prob']]
    
    @staticmethod
    @njit
    def _calculate_availability_prob(adp_array, target_pick):
        """使用 Numba 优化计算可用性概率"""
        prob_array = np.empty_like(adp_array, dtype=np.float64)
        
        for i in prange(len(adp_array)):
            adp = adp_array[i]
            # 使用正态分布模型计算可用性概率
            # ADP 越低，在目标位置被选中的概率越高
            if adp >= 999:
                prob_array[i] = 0.9  # 未被排名的球员有较高的可用性
            else:
                # 计算 Z-score
                z = (target_pick - adp) / 10  # 假设标准差为 10
                # 计算累积概率（球员在目标位置之前被选中的概率）
                prob_selected = 0.5 * (1 + np.tanh(z / np.sqrt(2)))
                # 可用性概率 = 1 - 被选中概率
                prob_array[i] = 1 - prob_selected
        
        return prob_array
    
    def generate_simulation_report(self, results):
        """生成模拟结果报告"""
        # 分析选秀结果
        all_picks = []
        for result in results:
            all_picks.extend(result['draft_picks'])
        
        picks_df = pd.DataFrame(all_picks)
        
        # 计算每个球员的平均选秀位置
        player_analysis = picks_df.groupby('player_id').agg({
            'pick_number': ['mean', 'std', 'count'],
            'player_name': 'first',
            'position': 'first',
            'vorp': 'first',
            'adp': 'first'
        }).reset_index()
        
        # 重命名列
        player_analysis.columns = ['player_id', 'avg_pick', 'std_pick', 'times_drafted', 'player_name', 'position', 'vorp', 'adp']
        
        # 计算价值差异（VORP 与平均选秀位置的比率）
        player_analysis['value_per_pick'] = player_analysis['vorp'] / player_analysis['avg_pick']
        
        # 分析策略效果
        strategy_analysis = picks_df.groupby('strategy').agg({
            'vorp': 'mean',
            'pick_number': 'mean'
        }).reset_index()
        
        return {
            'player_analysis': player_analysis,
            'strategy_analysis': strategy_analysis,
            'total_simulations': len(results)
        }

@njit(parallel=True)
def simulate_multiple_drafts(engine, iterations):
    """使用 Numba 并行运行多次选秀模拟"""
    results = []
    
    for i in prange(iterations):
        result = engine._run_single_simulation()
        results.append(result)
    
    return results