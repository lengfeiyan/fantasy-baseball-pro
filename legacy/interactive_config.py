#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式配置工具
帮助用户更方便地修改配置文件，无需手动编辑YAML
"""

import os
import yaml
from typing import Dict, Any


class InteractiveConfig:
    """交互式配置类"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        初始化交互式配置
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if not os.path.exists(self.config_path):
            # 如果配置文件不存在，返回默认配置
            return self._get_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            'data': {
                'use_multi_source': True,
                'file_patterns': {
                    'hitters': 'hitters_2026_{source}.csv',
                    'pitchers': 'pitchers_2026_{source}.csv'
                },
                'positions_file': 'data/player_positions_2025.csv'
            },
            'projections': {
                'weights': {
                    'STEAMER': 0.7,
                    'ZIPS': 0.3
                },
                'sources': ['STEAMER', 'ZIPS']
            },
            'league': {
                'size': 12,
                'rounds': 15,
                'roster_slots': {
                    'C': 1,
                    '1B': 1,
                    '2B': 1,
                    '3B': 1,
                    'SS': 1,
                    'OF': 4,
                    'SP': 4,
                    'RP': 3,
                    'UTIL': 1
                },
                'scoring': {
                    'hitters': {
                        'R': 1,
                        'HR': 1,
                        'RBI': 1,
                        'SB': 1,
                        'AVG': 1
                    },
                    'pitchers': {
                        'W': 1,
                        'SV': 1,
                        'HOLD': 1,
                        'ERA': -1,
                        'WHIP': -1,
                        'K_per_9': 1
                    }
                }
            },
            'draft_simulator': {
                'default_strategy': 'balanced',
                'show_value_picks': True,
                'adp_file': 'adp.csv'
            },
            'risk_model': {
                'method': 'z_score',
                'adjustment_factor': 0.1
            },
            'logging': {
                'level': 'INFO',
                'file': 'fantasy_baseball.log'
            }
        }
    
    def _save_config(self) -> None:
        """
        保存配置文件
        """
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        print(f"✅ 配置已保存到: {self.config_path}")
    
    def run(self) -> None:
        """
        运行交互式配置
        """
        print("=== Fantasy Baseball 交互式配置工具 ===")
        print("欢迎使用交互式配置工具！在这里你可以轻松修改配置文件。")
        print("\n输入 'help' 查看可用命令，输入 'exit' 退出。")
        
        while True:
            print("\n当前配置:")
            self._display_current_config()
            
            command = input("\n请输入命令: ").strip().lower()
            
            if command == 'exit':
                print("再见！")
                break
            elif command == 'help':
                self._show_help()
            elif command == '1':
                self._configure_data()
            elif command == '2':
                self._configure_projections()
            elif command == '3':
                self._configure_league()
            elif command == '4':
                self._configure_draft_simulator()
            elif command == '5':
                self._configure_risk_model()
            elif command == '6':
                self._configure_logging()
            elif command == 'save':
                self._save_config()
            else:
                print("❌ 无效命令，请输入 'help' 查看可用命令。")
    
    def _display_current_config(self) -> None:
        """
        显示当前配置
        """
        print("1. 数据配置")
        print(f"   多源融合: {'开启' if self.config['data']['use_multi_source'] else '关闭'}")
        print(f"   位置映射文件: {self.config['data']['positions_file']}")
        
        print("2. 预测源配置")
        for source, weight in self.config['projections']['weights'].items():
            print(f"   {source}: {weight:.2f}")
        
        print("3. 联盟配置")
        print(f"   联盟规模: {self.config['league']['size']} 队")
        print(f"   选秀轮数: {self.config['league']['rounds']} 轮")
        print("   阵容槽位:")
        for pos, count in self.config['league']['roster_slots'].items():
            print(f"     {pos}: {count}")
        
        print("4. 选秀模拟器配置")
        print(f"   默认策略: {self.config['draft_simulator']['default_strategy']}")
        print(f"   价值股提示: {'开启' if self.config['draft_simulator']['show_value_picks'] else '关闭'}")
        
        print("5. 风险模型配置")
        print(f"   计算方法: {self.config['risk_model']['method']}")
        print(f"   调整系数: {self.config['risk_model']['adjustment_factor']}")
        
        print("6. 日志配置")
        print(f"   日志级别: {self.config['logging']['level']}")
        print(f"   日志文件: {self.config['logging']['file']}")
    
    def _show_help(self) -> None:
        """
        显示帮助信息
        """
        print("\n可用命令:")
        print("1 - 配置数据处理")
        print("2 - 配置预测源权重")
        print("3 - 配置联盟规则")
        print("4 - 配置选秀模拟器")
        print("5 - 配置风险模型")
        print("6 - 配置日志")
        print("save - 保存配置")
        print("help - 显示帮助")
        print("exit - 退出")
    
    def _configure_data(self) -> None:
        """
        配置数据处理
        """
        print("\n=== 配置数据处理 ===")
        
        # 配置多源融合
        use_multi = input("是否开启多源预测融合？(y/n): ").strip().lower()
        self.config['data']['use_multi_source'] = (use_multi == 'y')
        
        # 配置位置映射文件
        positions_file = input(f"位置映射文件路径 [{self.config['data']['positions_file']}]: ").strip()
        if positions_file:
            self.config['data']['positions_file'] = positions_file
        
        print("✅ 数据配置已更新")
    
    def _configure_projections(self) -> None:
        """
        配置预测源权重
        """
        print("\n=== 配置预测源权重 ===")
        
        # 配置STEAMER权重
        steamer_weight = input(f"STEAMER 权重 [{self.config['projections']['weights'].get('STEAMER', 0.7)}]: ").strip()
        if steamer_weight:
            try:
                weight = float(steamer_weight)
                if 0 <= weight <= 1:
                    self.config['projections']['weights']['STEAMER'] = weight
                else:
                    print("⚠️ 权重必须在0-1之间，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        # 配置ZIPS权重
        zips_weight = input(f"ZIPS 权重 [{self.config['projections']['weights'].get('ZIPS', 0.3)}]: ").strip()
        if zips_weight:
            try:
                weight = float(zips_weight)
                if 0 <= weight <= 1:
                    self.config['projections']['weights']['ZIPS'] = weight
                else:
                    print("⚠️ 权重必须在0-1之间，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        # 配置THE BAT权重（可选）
        the_bat_weight = input(f"THE BAT 权重 [{self.config['projections']['weights'].get('THE_BAT', 0)}]: ").strip()
        if the_bat_weight:
            try:
                weight = float(the_bat_weight)
                if 0 <= weight <= 1:
                    self.config['projections']['weights']['THE_BAT'] = weight
                else:
                    print("⚠️ 权重必须在0-1之间，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        # 更新sources列表
        self.config['projections']['sources'] = [source for source, weight in self.config['projections']['weights'].items() if weight > 0]
        
        # 验证权重总和
        total_weight = sum(self.config['projections']['weights'].values())
        if abs(total_weight - 1.0) > 0.001:
            print(f"⚠️ 权重总和为 {total_weight:.2f}，建议调整为1.0。")
        
        print("✅ 预测源配置已更新")
    
    def _configure_league(self) -> None:
        """
        配置联盟规则
        """
        print("\n=== 配置联盟规则 ===")
        
        # 配置联盟规模
        league_size = input(f"联盟规模 (球队数量) [{self.config['league']['size']}]: ").strip()
        if league_size:
            try:
                size = int(league_size)
                if size >= 4:
                    self.config['league']['size'] = size
                else:
                    print("⚠️ 联盟规模至少为4，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        # 配置选秀轮数
        rounds = input(f"选秀轮数 [{self.config['league']['rounds']}]: ").strip()
        if rounds:
            try:
                r = int(rounds)
                if r >= 5:
                    self.config['league']['rounds'] = r
                else:
                    print("⚠️ 选秀轮数至少为5，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        # 配置阵容槽位
        print("\n阵容槽位配置:")
        for pos in self.config['league']['roster_slots']:
            count = input(f"{pos}: [{self.config['league']['roster_slots'][pos]}]: ").strip()
            if count:
                try:
                    c = int(count)
                    if c >= 0:
                        self.config['league']['roster_slots'][pos] = c
                    else:
                        print("⚠️ 数量不能为负数，使用默认值。")
                except ValueError:
                    print("⚠️ 无效输入，使用默认值。")
        
        print("✅ 联盟配置已更新")
    
    def _configure_draft_simulator(self) -> None:
        """
        配置选秀模拟器
        """
        print("\n=== 配置选秀模拟器 ===")
        
        # 配置默认策略
        print("可选策略:")
        print("  conservative - 保守策略（优先选择下限高的球员）")
        print("  balanced - 平衡策略（使用标准VORP）")
        print("  aggressive - 激进策略（优先选择上限高的球员）")
        
        strategy = input(f"默认选秀策略 [{self.config['draft_simulator']['default_strategy']}]: ").strip().lower()
        if strategy in ['conservative', 'balanced', 'aggressive']:
            self.config['draft_simulator']['default_strategy'] = strategy
        elif strategy:
            print("⚠️ 无效策略，使用默认值。")
        
        # 配置价值股提示
        show_value = input(f"是否显示价值股提示？(y/n) [{('y' if self.config['draft_simulator']['show_value_picks'] else 'n')}]: ").strip().lower()
        if show_value:
            self.config['draft_simulator']['show_value_picks'] = (show_value == 'y')
        
        print("✅ 选秀模拟器配置已更新")
    
    def _configure_risk_model(self) -> None:
        """
        配置风险模型
        """
        print("\n=== 配置风险模型 ===")
        
        # 配置风险计算方法
        print("可选风险计算方法:")
        print("  z_score - 使用Z-score方法（基于标准差）")
        print("  historical_variance - 使用历史方差方法")
        
        method = input(f"风险计算方法 [{self.config['risk_model']['method']}]: ").strip().lower()
        if method in ['z_score', 'historical_variance']:
            self.config['risk_model']['method'] = method
        elif method:
            print("⚠️ 无效方法，使用默认值。")
        
        # 配置调整系数
        adjustment = input(f"风险调整系数 [{self.config['risk_model']['adjustment_factor']}]: ").strip()
        if adjustment:
            try:
                factor = float(adjustment)
                if 0 <= factor <= 1:
                    self.config['risk_model']['adjustment_factor'] = factor
                else:
                    print("⚠️ 调整系数必须在0-1之间，使用默认值。")
            except ValueError:
                print("⚠️ 无效输入，使用默认值。")
        
        print("✅ 风险模型配置已更新")
    
    def _configure_logging(self) -> None:
        """
        配置日志
        """
        print("\n=== 配置日志 ===")
        
        # 配置日志级别
        print("可选日志级别:")
        print("  DEBUG - 详细信息")
        print("  INFO - 一般信息（默认）")
        print("  WARNING - 警告信息")
        print("  ERROR - 错误信息")
        
        level = input(f"日志级别 [{self.config['logging']['level']}]: ").strip().upper()
        if level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            self.config['logging']['level'] = level
        elif level:
            print("⚠️ 无效日志级别，使用默认值。")
        
        # 配置日志文件
        log_file = input(f"日志文件路径 [{self.config['logging']['file']}]: ").strip()
        if log_file:
            self.config['logging']['file'] = log_file
        
        print("✅ 日志配置已更新")


def main():
    """
    主函数
    """
    config_tool = InteractiveConfig()
    config_tool.run()


if __name__ == '__main__':
    main()
