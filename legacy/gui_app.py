#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fantasy Baseball Pro GUI应用
提供图形化界面，方便用户操作所有功能
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import queue

# 添加日志功能
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('gui_app')


class FantasyBaseballGUI:
    """Fantasy Baseball Pro GUI应用类"""
    
    def __init__(self, root):
        """
        初始化GUI应用
        
        Args:
            root: Tkinter根窗口
        """
        logger.info("=========================================")
        logger.info("开始启动 Fantasy Baseball Pro GUI 应用")
        logger.info("=========================================")
        
        self.root = root
        self.root.title("Fantasy Baseball Pro")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        logger.info("设置窗口属性成功")
        
        # 设置图标（如果有的话）
        # self.root.iconbitmap('icon.ico')
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        logger.info("创建主框架成功")
        
        # 创建选项卡
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        logger.info("创建选项卡控件成功")
        
        # 创建各个选项卡
        logger.info("开始创建各个功能选项卡...")
        self.create_home_tab()
        self.create_data_tab()
        self.create_config_tab()
        self.create_analysis_tab()
        self.create_draft_tab()
        self.create_roster_tab()
        self.create_sleeper_tab()
        self.create_dynamic_draft_tab()
        self.create_fa_analysis_tab()
        self.create_plugin_tab()
        logger.info("所有选项卡创建完成")
        
        logger.info("=========================================")
        logger.info("Fantasy Baseball Pro GUI 应用启动完成")
        logger.info("=========================================")
        self.create_help_tab()
        
        # 创建状态条
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建命令队列
        self.cmd_queue = queue.Queue()
        
        # 启动命令处理线程
        self.cmd_thread = threading.Thread(target=self.process_commands, daemon=True)
        self.cmd_thread.start()
    
    def create_home_tab(self):
        """
        创建主页选项卡
        """
        home_tab = ttk.Frame(self.notebook)
        self.notebook.add(home_tab, text="主页")
        
        # 创建欢迎信息
        welcome_frame = ttk.Frame(home_tab, padding="20")
        welcome_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(welcome_frame, text="Fantasy Baseball Pro", font=("Arial", 24, "bold"))
        title_label.pack(pady=20)
        
        subtitle_label = ttk.Label(welcome_frame, text="专业级Fantasy Baseball分析与选秀模拟系统", font=("Arial", 14))
        subtitle_label.pack(pady=10)
        
        features_frame = ttk.LabelFrame(welcome_frame, text="主要功能", padding="10")
        features_frame.pack(fill=tk.X, pady=20)
        
        features = [
            "• 多源预测数据融合",
            "• VORP + 风险评分系统",
            "• 蛇形选秀模拟",
            "• 阵容合规性检查",
            "• 交互式配置工具"
        ]
        
        for feature in features:
            feature_label = ttk.Label(features_frame, text=feature, font=("Arial", 10))
            feature_label.pack(anchor=tk.W, pady=5)
        
        quick_start_frame = ttk.LabelFrame(welcome_frame, text="快速开始", padding="10")
        quick_start_frame.pack(fill=tk.X, pady=10)
        
        quick_start_steps = [
            "1. 在'数据管理'选项卡中导入CSV数据",
            "2. 在'配置设置'选项卡中配置联盟规则",
            "3. 在'分析流水线'选项卡中运行分析",
            "4. 在'选秀模拟'选项卡中模拟选秀",
            "5. 在'阵容验证'选项卡中检查阵容"
        ]
        
        for step in quick_start_steps:
            step_label = ttk.Label(quick_start_frame, text=step, font=("Arial", 10))
            step_label.pack(anchor=tk.W, pady=3)
    
    def create_data_tab(self):
        """
        创建数据管理选项卡
        """
        data_tab = ttk.Frame(self.notebook)
        self.notebook.add(data_tab, text="数据管理")
        
        data_frame = ttk.Frame(data_tab, padding="20")
        data_frame.pack(fill=tk.BOTH, expand=True)
        
        # 数据文件选择
        file_frame = ttk.LabelFrame(data_frame, text="数据文件", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        # 位置映射文件
        pos_file_frame = ttk.Frame(file_frame)
        pos_file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pos_file_frame, text="位置映射文件:", width=20).pack(side=tk.LEFT)
        self.pos_file_var = tk.StringVar()
        self.pos_file_var.set("data/player_positions_2025.csv")
        ttk.Entry(pos_file_frame, textvariable=self.pos_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(pos_file_frame, text="浏览", command=self.browse_pos_file).pack(side=tk.RIGHT)
        
        # 打者数据文件
        hitters_frame = ttk.Frame(file_frame)
        hitters_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(hitters_frame, text="打者数据文件:", width=20).pack(side=tk.LEFT)
        self.hitters_file_var = tk.StringVar()
        self.hitters_file_var.set("data/hitters_2026_steamer.csv")
        ttk.Entry(hitters_frame, textvariable=self.hitters_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(hitters_frame, text="浏览", command=self.browse_hitters_file).pack(side=tk.RIGHT)
        
        # 投手数据文件
        pitchers_frame = ttk.Frame(file_frame)
        pitchers_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pitchers_frame, text="投手数据文件:", width=20).pack(side=tk.LEFT)
        self.pitchers_file_var = tk.StringVar()
        self.pitchers_file_var.set("data/pitchers_2026_steamer.csv")
        ttk.Entry(pitchers_frame, textvariable=self.pitchers_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(pitchers_frame, text="浏览", command=self.browse_pitchers_file).pack(side=tk.RIGHT)
        
        # 多源融合选项
        multi_source_frame = ttk.Frame(data_frame, padding="10")
        multi_source_frame.pack(fill=tk.X, pady=10)
        
        self.multi_source_var = tk.BooleanVar()
        self.multi_source_var.set(True)
        ttk.Checkbutton(multi_source_frame, text="启用多源融合", variable=self.multi_source_var).pack(anchor=tk.W)
        
        # 导入按钮
        import_frame = ttk.Frame(data_frame)
        import_frame.pack(fill=tk.X, pady=20)
        
        self.import_button = ttk.Button(import_frame, text="导入数据", command=self.import_data, style="Accent.TButton")
        self.import_button.pack(side=tk.LEFT)
        
        # 日志文本框
        log_frame = ttk.LabelFrame(data_frame, text="导入日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.import_log = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.import_log.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.import_log, orient=tk.VERTICAL, command=self.import_log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.import_log.config(yscrollcommand=scrollbar.set)
    
    def create_config_tab(self):
        """
        创建配置设置选项卡
        """
        config_tab = ttk.Frame(self.notebook)
        self.notebook.add(config_tab, text="配置设置")
        
        config_frame = ttk.Frame(config_tab, padding="20")
        config_frame.pack(fill=tk.BOTH, expand=True)
        
        # 联盟设置
        league_frame = ttk.LabelFrame(config_frame, text="联盟设置", padding="10")
        league_frame.pack(fill=tk.X, pady=10)
        
        # 联盟规模
        size_frame = ttk.Frame(league_frame)
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="联盟规模:", width=20).pack(side=tk.LEFT)
        self.league_size_var = tk.StringVar()
        self.league_size_var.set("12")
        ttk.Combobox(size_frame, textvariable=self.league_size_var, values=["8", "10", "12", "14", "16"], width=10).pack(side=tk.LEFT)
        
        # 选秀轮数
        rounds_frame = ttk.Frame(league_frame)
        rounds_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(rounds_frame, text="选秀轮数:", width=20).pack(side=tk.LEFT)
        self.league_rounds_var = tk.StringVar()
        self.league_rounds_var.set("15")
        ttk.Combobox(rounds_frame, textvariable=self.league_rounds_var, values=["10", "12", "15", "18", "20"], width=10).pack(side=tk.LEFT)
        
        # 阵容槽位
        roster_frame = ttk.LabelFrame(config_frame, text="阵容槽位", padding="10")
        roster_frame.pack(fill=tk.X, pady=10)
        
        positions = ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "UTIL"]
        self.roster_vars = {}
        
        for i, pos in enumerate(positions):
            pos_frame = ttk.Frame(roster_frame)
            pos_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(pos_frame, text=f"{pos}:", width=10).pack(side=tk.LEFT)
            var = tk.StringVar()
            var.set("1" if pos != "OF" else "4" if pos == "OF" else "4" if pos == "SP" else "3" if pos == "RP" else "1")
            self.roster_vars[pos] = var
            ttk.Entry(pos_frame, textvariable=var, width=5).pack(side=tk.LEFT)
        
        # 选秀策略
        strategy_frame = ttk.LabelFrame(config_frame, text="选秀策略", padding="10")
        strategy_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(strategy_frame, text="默认策略:", width=20).pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar()
        self.strategy_var.set("balanced")
        ttk.Combobox(strategy_frame, textvariable=self.strategy_var, values=["conservative", "balanced", "aggressive"], width=15).pack(side=tk.LEFT)
        
        # 保存按钮
        save_frame = ttk.Frame(config_frame)
        save_frame.pack(fill=tk.X, pady=20)
        
        self.save_config_button = ttk.Button(save_frame, text="保存配置", command=self.save_config, style="Accent.TButton")
        self.save_config_button.pack(side=tk.LEFT)
    
    def create_analysis_tab(self):
        """
        创建分析流水线选项卡
        """
        analysis_tab = ttk.Frame(self.notebook)
        self.notebook.add(analysis_tab, text="分析流水线")
        
        analysis_frame = ttk.Frame(analysis_tab, padding="20")
        analysis_frame.pack(fill=tk.BOTH, expand=True)
        
        # 分析步骤
        steps_frame = ttk.LabelFrame(analysis_frame, text="分析步骤", padding="10")
        steps_frame.pack(fill=tk.X, pady=10)
        
        steps = [
            ("导入数据", self.import_data),
            ("数据质量校验", self.validate_data_quality),
            ("生成排名", self.generate_rankings),
            ("获取ADP", self.fetch_adp),
            ("运行完整流水线", self.run_full_pipeline)
        ]
        
        for step_name, step_command in steps:
            step_frame = ttk.Frame(steps_frame)
            step_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(step_frame, text=step_name, command=step_command).pack(side=tk.LEFT)
        
        # 排名文件
        rankings_frame = ttk.LabelFrame(analysis_frame, text="排名结果", padding="10")
        rankings_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.rankings_list = tk.Listbox(rankings_frame)
        self.rankings_list.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.rankings_list, orient=tk.VERTICAL, command=self.rankings_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rankings_list.config(yscrollcommand=scrollbar.set)
        
        # 刷新按钮
        refresh_frame = ttk.Frame(rankings_frame)
        refresh_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(refresh_frame, text="刷新列表", command=self.refresh_rankings).pack(side=tk.LEFT)
    
    def create_draft_tab(self):
        """
        创建选秀模拟选项卡
        """
        draft_tab = ttk.Frame(self.notebook)
        self.notebook.add(draft_tab, text="选秀模拟")
        
        draft_frame = ttk.Frame(draft_tab, padding="20")
        draft_frame.pack(fill=tk.BOTH, expand=True)
        
        # 选秀设置
        draft_settings_frame = ttk.LabelFrame(draft_frame, text="选秀设置", padding="10")
        draft_settings_frame.pack(fill=tk.X, pady=10)
        
        # 选秀顺位
        pick_frame = ttk.Frame(draft_settings_frame)
        pick_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pick_frame, text="选秀顺位:", width=20).pack(side=tk.LEFT)
        self.draft_pick_var = tk.StringVar()
        self.draft_pick_var.set("5")
        ttk.Combobox(pick_frame, textvariable=self.draft_pick_var, values=[str(i) for i in range(1, 13)], width=5).pack(side=tk.LEFT)
        
        # 选秀策略
        draft_strategy_frame = ttk.Frame(draft_settings_frame)
        draft_strategy_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(draft_strategy_frame, text="选秀策略:", width=20).pack(side=tk.LEFT)
        self.draft_strategy_var = tk.StringVar()
        self.draft_strategy_var.set("balanced")
        ttk.Combobox(draft_strategy_frame, textvariable=self.draft_strategy_var, values=["conservative", "balanced", "aggressive"], width=15).pack(side=tk.LEFT)
        
        # 模拟按钮
        simulate_frame = ttk.Frame(draft_frame)
        simulate_frame.pack(fill=tk.X, pady=20)
        
        self.simulate_button = ttk.Button(simulate_frame, text="模拟选秀", command=self.simulate_draft, style="Accent.TButton")
        self.simulate_button.pack(side=tk.LEFT)
        
        # 选秀日志
        draft_log_frame = ttk.LabelFrame(draft_frame, text="选秀日志", padding="10")
        draft_log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.draft_log = tk.Text(draft_log_frame, height=15, wrap=tk.WORD)
        self.draft_log.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.draft_log, orient=tk.VERTICAL, command=self.draft_log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.draft_log.config(yscrollcommand=scrollbar.set)
    
    def create_roster_tab(self):
        """
        创建阵容验证选项卡
        """
        roster_tab = ttk.Frame(self.notebook)
        self.notebook.add(roster_tab, text="阵容验证")
        
        roster_frame = ttk.Frame(roster_tab, padding="20")
        roster_frame.pack(fill=tk.BOTH, expand=True)
        
        # 选秀日志文件
        log_file_frame = ttk.Frame(roster_frame)
        log_file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(log_file_frame, text="选秀日志文件:", width=20).pack(side=tk.LEFT)
        self.roster_log_var = tk.StringVar()
        self.roster_log_var.set("draft_log_pick5_balanced.csv")
        ttk.Entry(log_file_frame, textvariable=self.roster_log_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(log_file_frame, text="浏览", command=self.browse_roster_log).pack(side=tk.RIGHT)
        
        # 验证按钮
        validate_frame = ttk.Frame(roster_frame)
        validate_frame.pack(fill=tk.X, pady=20)
        
        self.validate_button = ttk.Button(validate_frame, text="验证阵容", command=self.validate_roster, style="Accent.TButton")
        self.validate_button.pack(side=tk.LEFT)
        
        # 验证结果
        result_frame = ttk.LabelFrame(roster_frame, text="验证结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.roster_result = tk.Text(result_frame, height=15, wrap=tk.WORD)
        self.roster_result.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.roster_result, orient=tk.VERTICAL, command=self.roster_result.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.roster_result.config(yscrollcommand=scrollbar.set)
    
    def create_statcast_tab(self):
        """
        创建Statcast数据选项卡
        """
        statcast_tab = ttk.Frame(self.notebook)
        self.notebook.add(statcast_tab, text="Statcast分析")
        
        statcast_frame = ttk.Frame(statcast_tab, padding="20")
        statcast_frame.pack(fill=tk.BOTH, expand=True)
        
        # Statcast数据获取
        fetch_frame = ttk.LabelFrame(statcast_frame, text="数据获取", padding="10")
        fetch_frame.pack(fill=tk.X, pady=10)
        
        self.statcast_update_var = tk.BooleanVar()
        self.statcast_update_var.set(True)
        ttk.Checkbutton(fetch_frame, text="强制更新数据", variable=self.statcast_update_var).pack(anchor=tk.W)
        
        ttk.Button(fetch_frame, text="获取Statcast数据", command=self.fetch_statcast_data).pack(side=tk.LEFT, pady=5)
        
        # 球员搜索
        search_frame = ttk.LabelFrame(statcast_frame, text="球员搜索", padding="10")
        search_frame.pack(fill=tk.X, pady=10)
        
        search_inner_frame = ttk.Frame(search_frame)
        search_inner_frame.pack(fill=tk.X)
        
        ttk.Label(search_inner_frame, text="球员姓名:", width=15).pack(side=tk.LEFT)
        self.player_search_var = tk.StringVar()
        ttk.Entry(search_inner_frame, textvariable=self.player_search_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(search_inner_frame, text="搜索", command=self.search_player_statcast).pack(side=tk.RIGHT)
        
        # Statcast数据展示
        data_frame = ttk.LabelFrame(statcast_frame, text="Statcast数据", padding="10")
        data_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.statcast_data_text = tk.Text(data_frame, height=15, wrap=tk.WORD)
        self.statcast_data_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.statcast_data_text, orient=tk.VERTICAL, command=self.statcast_data_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.statcast_data_text.config(yscrollcommand=scrollbar.set)
    
    def create_injury_tab(self):
        """
        创建伤病风险分析选项卡
        """
        injury_tab = ttk.Frame(self.notebook)
        self.notebook.add(injury_tab, text="伤病风险")
        
        injury_frame = ttk.Frame(injury_tab, padding="20")
        injury_frame.pack(fill=tk.BOTH, expand=True)
        
        # 伤病数据更新
        update_frame = ttk.LabelFrame(injury_frame, text="数据更新", padding="10")
        update_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(update_frame, text="更新伤病数据", command=self.update_injury_data).pack(side=tk.LEFT)
        
        # 球员伤病风险分析
        analysis_frame = ttk.LabelFrame(injury_frame, text="风险分析", padding="10")
        analysis_frame.pack(fill=tk.X, pady=10)
        
        analysis_inner_frame = ttk.Frame(analysis_frame)
        analysis_inner_frame.pack(fill=tk.X)
        
        ttk.Label(analysis_inner_frame, text="球员ID:", width=15).pack(side=tk.LEFT)
        self.player_id_var = tk.StringVar()
        ttk.Entry(analysis_inner_frame, textvariable=self.player_id_var, width=20).pack(side=tk.LEFT)
        ttk.Button(analysis_inner_frame, text="分析风险", command=self.analyze_injury_risk).pack(side=tk.RIGHT)
        
        # 风险分析结果
        result_frame = ttk.LabelFrame(injury_frame, text="分析结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.injury_result_text = tk.Text(result_frame, height=15, wrap=tk.WORD)
        self.injury_result_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.injury_result_text, orient=tk.VERTICAL, command=self.injury_result_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.injury_result_text.config(yscrollcommand=scrollbar.set)
    
    def create_sleeper_tab(self):
        """
        创建Sleeper推荐器选项卡
        """
        sleeper_tab = ttk.Frame(self.notebook)
        self.notebook.add(sleeper_tab, text="Sleeper推荐")
        
        sleeper_frame = ttk.Frame(sleeper_tab, padding="20")
        sleeper_frame.pack(fill=tk.BOTH, expand=True)
        
        # 脚本选择
        script_frame = ttk.LabelFrame(sleeper_frame, text="脚本选择", padding="10")
        script_frame.pack(fill=tk.X, pady=10)
        
        self.script_var = tk.StringVar()
        self.script_var.set("basic")
        
        ttk.Radiobutton(script_frame, text="基础版 (VORP vs ADP)", variable=self.script_var, value="basic").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(script_frame, text="Statcast 增强版", variable=self.script_var, value="statcast").pack(anchor=tk.W, pady=2)
        
        # 参数配置
        params_frame = ttk.LabelFrame(sleeper_frame, text="参数配置", padding="10")
        params_frame.pack(fill=tk.X, pady=10)
        
        # 最小ADP
        min_adp_frame = ttk.Frame(params_frame)
        min_adp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(min_adp_frame, text="最小ADP:", width=15).pack(side=tk.LEFT)
        self.min_adp_var = tk.StringVar()
        self.min_adp_var.set("80")
        ttk.Entry(min_adp_frame, textvariable=self.min_adp_var, width=10).pack(side=tk.LEFT)
        
        # 最大ADP
        max_adp_frame = ttk.Frame(params_frame)
        max_adp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(max_adp_frame, text="最大ADP:", width=15).pack(side=tk.LEFT)
        self.max_adp_var = tk.StringVar()
        self.max_adp_var.set("300")
        ttk.Entry(max_adp_frame, textvariable=self.max_adp_var, width=10).pack(side=tk.LEFT)
        
        # 最小低估顺位
        min_bias_frame = ttk.Frame(params_frame)
        min_bias_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(min_bias_frame, text="最小低估顺位:", width=15).pack(side=tk.LEFT)
        self.min_bias_var = tk.StringVar()
        self.min_bias_var.set("30")
        ttk.Entry(min_bias_frame, textvariable=self.min_bias_var, width=10).pack(side=tk.LEFT)
        
        # 位置筛选
        position_frame = ttk.Frame(params_frame)
        position_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(position_frame, text="位置筛选:", width=15).pack(side=tk.LEFT)
        self.position_var = tk.StringVar()
        self.position_var.set("All")
        ttk.Combobox(position_frame, textvariable=self.position_var, 
                     values=["All", "C", "1B", "2B", "3B", "SS", "OF", "SP", "RP", "UTIL"], 
                     width=10).pack(side=tk.LEFT)
        
        # 输出数量
        top_frame = ttk.Frame(params_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(top_frame, text="输出数量:", width=15).pack(side=tk.LEFT)
        self.top_var = tk.StringVar()
        self.top_var.set("20")
        ttk.Entry(top_frame, textvariable=self.top_var, width=10).pack(side=tk.LEFT)
        
        # 执行按钮
        execute_frame = ttk.Frame(sleeper_frame)
        execute_frame.pack(fill=tk.X, pady=20)
        
        self.execute_button = ttk.Button(execute_frame, text="执行Sleeper分析", command=self.execute_sleeper, style="Accent.TButton")
        self.execute_button.pack(side=tk.LEFT)
        
        # 结果文本框
        result_frame = ttk.LabelFrame(sleeper_frame, text="分析结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.sleeper_result_text = tk.Text(result_frame, height=20, wrap=tk.WORD)
        self.sleeper_result_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.sleeper_result_text, orient=tk.VERTICAL, command=self.sleeper_result_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sleeper_result_text.config(yscrollcommand=scrollbar.set)
    
    def execute_sleeper(self):
        """
        执行Sleeper分析
        """
        script_type = self.script_var.get()
        min_adp = self.min_adp_var.get()
        max_adp = self.max_adp_var.get()
        min_bias = self.min_bias_var.get()
        position = self.position_var.get()
        top = self.top_var.get()
        
        logger.info(f"开始执行Sleeper分析:")
        logger.info(f"- 脚本类型: {script_type}")
        logger.info(f"- 最小ADP: {min_adp}")
        logger.info(f"- 最大ADP: {max_adp}")
        logger.info(f"- 最小低估顺位: {min_bias}")
        logger.info(f"- 位置: {position}")
        logger.info(f"- 输出数量: {top}")
        
        self.status_var.set("正在执行Sleeper分析...")
        self.sleeper_result_text.delete(1.0, tk.END)
        
        # 创建线程执行分析
        sleeper_thread = threading.Thread(target=self._execute_sleeper_thread, 
                                         args=(script_type, min_adp, max_adp, min_bias, position, top))
        sleeper_thread.daemon = True
        sleeper_thread.start()
        logger.info("Sleeper分析线程已启动")
    
    def _execute_sleeper_thread(self, script_type, min_adp, max_adp, min_bias, position, top):
        """
        执行Sleeper分析线程
        """
        try:
            # 构建命令
            if script_type == "basic":
                cmd = [sys.executable, "find_sleeper_players.py"]
            else:
                cmd = [sys.executable, "find_sleeper_players_statcast_v2.0.py"]
            
            # 添加参数
            cmd.extend(["--min-adp", min_adp])
            cmd.extend(["--max-adp", max_adp])
            cmd.extend(["--min-bias", min_bias])
            cmd.extend(["--top", top])
            
            # 添加位置参数（如果不是All）
            if position != "All":
                cmd.extend(["--position", position])
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 执行命令
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            output_lines = []
            for line in process.stdout:
                output_lines.append(line)
                self.root.after(0, self.sleeper_result_text.insert, tk.END, line)
                self.root.after(0, self.sleeper_result_text.see, tk.END)
            
            process.wait()
            
            logger.info(f"命令执行完成，返回码: {process.returncode}")
            
            if process.returncode == 0:
                logger.info("Sleeper分析执行成功")
                self.root.after(0, self.status_var.set, "Sleeper分析完成")
                self.root.after(0, messagebox.showinfo, "成功", "Sleeper分析完成！结果已保存至reports目录")
            else:
                error_output = ''.join(output_lines)
                logger.error(f"Sleeper分析执行失败: {error_output}")
                self.root.after(0, self.status_var.set, "Sleeper分析失败")
                self.root.after(0, messagebox.showerror, "错误", "Sleeper分析失败，请查看结果了解详情。")
        except Exception as e:
            error_msg = f"执行Sleeper分析时出错: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
    
    def create_dynamic_draft_tab(self):
        """
        创建动态选秀模拟器选项卡
        """
        dynamic_draft_tab = ttk.Frame(self.notebook)
        self.notebook.add(dynamic_draft_tab, text="动态选秀模拟")
        
        draft_frame = ttk.Frame(dynamic_draft_tab, padding="20")
        draft_frame.pack(fill=tk.BOTH, expand=True)
        
        # 参数配置
        params_frame = ttk.LabelFrame(draft_frame, text="模拟参数", padding="10")
        params_frame.pack(fill=tk.X, pady=10)
        
        # 选秀顺位
        pick_frame = ttk.Frame(params_frame)
        pick_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pick_frame, text="你的选秀顺位:", width=15).pack(side=tk.LEFT)
        self.user_pick_var = tk.StringVar()
        self.user_pick_var.set("8")
        ttk.Combobox(pick_frame, textvariable=self.user_pick_var, 
                     values=[str(i) for i in range(1, 13)], 
                     width=10).pack(side=tk.LEFT)
        
        # 模拟次数
        simulations_frame = ttk.Frame(params_frame)
        simulations_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(simulations_frame, text="模拟次数:", width=15).pack(side=tk.LEFT)
        self.simulations_var = tk.StringVar()
        self.simulations_var.set("10000")
        ttk.Entry(simulations_frame, textvariable=self.simulations_var, width=10).pack(side=tk.LEFT)
        
        # 最小可用率
        availability_frame = ttk.Frame(params_frame)
        availability_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(availability_frame, text="最小可用率:", width=15).pack(side=tk.LEFT)
        self.min_availability_var = tk.StringVar()
        self.min_availability_var.set("0.3")
        ttk.Entry(availability_frame, textvariable=self.min_availability_var, width=10).pack(side=tk.LEFT)
        ttk.Label(availability_frame, text=" (0-1，默认0.3)", width=20).pack(side=tk.LEFT)
        
        # 执行按钮
        execute_frame = ttk.Frame(draft_frame)
        execute_frame.pack(fill=tk.X, pady=20)
        
        self.execute_dynamic_draft_button = ttk.Button(execute_frame, text="执行动态选秀模拟", command=self.execute_dynamic_draft, style="Accent.TButton")
        self.execute_dynamic_draft_button.pack(side=tk.LEFT)
        
        # 结果文本框
        result_frame = ttk.LabelFrame(draft_frame, text="模拟结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.dynamic_draft_result_text = tk.Text(result_frame, height=20, wrap=tk.WORD)
        self.dynamic_draft_result_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.dynamic_draft_result_text, orient=tk.VERTICAL, command=self.dynamic_draft_result_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dynamic_draft_result_text.config(yscrollcommand=scrollbar.set)
    
    def execute_dynamic_draft(self):
        """
        执行动态选秀模拟
        """
        user_pick = self.user_pick_var.get()
        simulations = self.simulations_var.get()
        min_availability = self.min_availability_var.get()
        
        logger.info(f"开始执行动态选秀模拟:")
        logger.info(f"- 选秀顺位: {user_pick}")
        logger.info(f"- 模拟次数: {simulations}")
        logger.info(f"- 最小可用率: {min_availability}")
        
        self.status_var.set("正在执行动态选秀模拟...")
        self.dynamic_draft_result_text.delete(1.0, tk.END)
        
        # 创建线程执行模拟
        draft_thread = threading.Thread(target=self._execute_dynamic_draft_thread, 
                                       args=(user_pick, simulations, min_availability))
        draft_thread.daemon = True
        draft_thread.start()
        logger.info("动态选秀模拟线程已启动")
    
    def _execute_dynamic_draft_thread(self, user_pick, simulations, min_availability):
        """
        执行动态选秀模拟线程
        """
        try:
            # 构建命令
            cmd = [sys.executable, "-m", "draft_simulator.run_simulation"]
            cmd.extend(["--user-pick", user_pick])
            cmd.extend(["--simulations", simulations])
            cmd.extend(["--min-availability", min_availability])
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 执行命令
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            output_lines = []
            for line in process.stdout:
                output_lines.append(line)
                self.root.after(0, self.dynamic_draft_result_text.insert, tk.END, line)
                self.root.after(0, self.dynamic_draft_result_text.see, tk.END)
            
            process.wait()
            
            logger.info(f"命令执行完成，返回码: {process.returncode}")
            
            if process.returncode == 0:
                logger.info("动态选秀模拟执行成功")
                self.root.after(0, self.status_var.set, "动态选秀模拟完成")
                self.root.after(0, messagebox.showinfo, "成功", "动态选秀模拟完成！结果已保存至reports目录")
            else:
                error_output = ''.join(output_lines)
                logger.error(f"动态选秀模拟执行失败: {error_output}")
                self.root.after(0, self.status_var.set, "动态选秀模拟失败")
                self.root.after(0, messagebox.showerror, "错误", "动态选秀模拟失败，请查看结果了解详情。")
        except Exception as e:
            error_msg = f"执行动态选秀模拟时出错: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
    
    def create_plugin_tab(self):
        """
        创建插件管理选项卡
        """
        plugin_tab = ttk.Frame(self.notebook)
        self.notebook.add(plugin_tab, text="插件管理")
        
        plugin_frame = ttk.Frame(plugin_tab, padding="20")
        plugin_frame.pack(fill=tk.BOTH, expand=True)
        
        # 插件列表
        list_frame = ttk.LabelFrame(plugin_frame, text="已安装插件", padding="10")
        list_frame.pack(fill=tk.X, pady=10)
        
        self.plugin_list = tk.Listbox(list_frame, height=10)
        self.plugin_list.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.plugin_list, orient=tk.VERTICAL, command=self.plugin_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plugin_list.config(yscrollcommand=scrollbar.set)
        
        # 插件操作
        action_frame = ttk.Frame(plugin_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="刷新插件列表", command=self.refresh_plugins).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="启用插件", command=self.enable_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="禁用插件", command=self.disable_plugin).pack(side=tk.LEFT, padx=5)
        
        # 插件配置
        config_frame = ttk.LabelFrame(plugin_frame, text="插件配置", padding="10")
        config_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.plugin_config_text = tk.Text(config_frame, height=10, wrap=tk.WORD)
        self.plugin_config_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.plugin_config_text, orient=tk.VERTICAL, command=self.plugin_config_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plugin_config_text.config(yscrollcommand=scrollbar.set)
    
    def create_fa_analysis_tab(self):
        """
        创建FA分析选项卡
        """
        fa_tab = ttk.Frame(self.notebook)
        self.notebook.add(fa_tab, text="FA分析")
        
        fa_frame = ttk.Frame(fa_tab, padding="20")
        fa_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部功能按钮区
        button_frame = ttk.LabelFrame(fa_frame, text="数据管理", padding="10")
        button_frame.pack(fill=tk.X, pady=10)
        
        button_inner_frame = ttk.Frame(button_frame)
        button_inner_frame.pack(fill=tk.X)
        
        ttk.Button(button_inner_frame, text="更新FA池", command=self.update_fa_pool).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_inner_frame, text="更新伤病数据", command=self.update_injury_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_inner_frame, text="生成推荐", command=self.generate_fa_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_inner_frame, text="导出结果", command=self.export_fa_recommendations).pack(side=tk.LEFT, padx=5)
        
        # 筛选条件区
        filter_frame = ttk.LabelFrame(fa_frame, text="筛选条件", padding="10")
        filter_frame.pack(fill=tk.X, pady=10)
        
        # 位置筛选
        pos_frame = ttk.Frame(filter_frame)
        pos_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pos_frame, text="位置:", width=10).pack(side=tk.LEFT)
        self.fa_position_var = tk.StringVar()
        self.fa_position_var.set("All")
        ttk.Combobox(pos_frame, textvariable=self.fa_position_var, 
                     values=["All", "C", "1B", "2B", "3B", "SS", "OF", "SP", "RP"], 
                     width=10).pack(side=tk.LEFT, padx=5)
        
        # 风险偏好
        risk_frame = ttk.Frame(filter_frame)
        risk_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(risk_frame, text="风险偏好:", width=10).pack(side=tk.LEFT)
        self.fa_risk_var = tk.StringVar()
        self.fa_risk_var.set("balanced")
        ttk.Combobox(risk_frame, textvariable=self.fa_risk_var, 
                     values=["conservative", "balanced", "aggressive"], 
                     width=15).pack(side=tk.LEFT, padx=5)
        
        # 推荐数量
        top_frame = ttk.Frame(filter_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(top_frame, text="推荐数量:", width=10).pack(side=tk.LEFT)
        self.fa_top_var = tk.StringVar()
        self.fa_top_var.set("10")
        ttk.Entry(top_frame, textvariable=self.fa_top_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # FA球员列表
        list_frame = ttk.LabelFrame(fa_frame, text="FA球员列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建表格
        columns = ("rank", "name", "team", "pos", "value", "statcast", "risk")
        self.fa_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.fa_tree.heading("rank", text="排名")
        self.fa_tree.heading("name", text="球员")
        self.fa_tree.heading("team", text="球队")
        self.fa_tree.heading("pos", text="位置")
        self.fa_tree.heading("value", text="价值")
        self.fa_tree.heading("statcast", text="Statcast")
        self.fa_tree.heading("risk", text="风险")
        
        # 设置列宽
        self.fa_tree.column("rank", width=50)
        self.fa_tree.column("name", width=150)
        self.fa_tree.column("team", width=80)
        self.fa_tree.column("pos", width=50)
        self.fa_tree.column("value", width=80)
        self.fa_tree.column("statcast", width=80)
        self.fa_tree.column("risk", width=80)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.fa_tree.yview)
        self.fa_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.fa_tree.pack(fill=tk.BOTH, expand=True)
        
        # 详细信息区
        detail_frame = ttk.LabelFrame(fa_frame, text="球员详情", padding="10")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.fa_detail_text = tk.Text(detail_frame, height=15, wrap=tk.WORD)
        self.fa_detail_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.fa_detail_text, orient=tk.VERTICAL, command=self.fa_detail_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.fa_detail_text.config(yscrollcommand=scrollbar.set)
        
        # 绑定选择事件
        self.fa_tree.bind("<<TreeviewSelect>>", self.on_fa_player_select)
    
    def update_fa_pool(self):
        """
        更新FA池数据
        """
        self.status_var.set("正在更新FA池...")
        
        # 创建线程执行更新
        update_thread = threading.Thread(target=self._update_fa_pool_thread)
        update_thread.daemon = True
        update_thread.start()
    
    def _update_fa_pool_thread(self):
        """
        更新FA池线程
        """
        try:
            from fa_analyzer.real_time_data import RealTimeData
            rtd = RealTimeData()
            fa_players = rtd.update_fa_pool()
            
            self.root.after(0, self.status_var.set, f"FA池更新完成，共 {len(fa_players)} 名球员")
            self.root.after(0, messagebox.showinfo, "成功", f"FA池更新完成，共 {len(fa_players)} 名球员")
        except Exception as e:
            error_msg = f"更新FA池失败: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
    
    def update_injury_data(self):
        """
        更新伤病数据
        """
        self.status_var.set("正在更新伤病数据...")
        
        # 创建线程执行更新
        update_thread = threading.Thread(target=self._update_injury_data_thread)
        update_thread.daemon = True
        update_thread.start()
    
    def _update_injury_data_thread(self):
        """
        更新伤病数据线程
        """
        try:
            from fa_analyzer.real_time_data import RealTimeData
            rtd = RealTimeData()
            injury_reports = rtd.update_injury_data()
            
            self.root.after(0, self.status_var.set, f"伤病数据更新完成，共 {len(injury_reports)} 条伤病报告")
            self.root.after(0, messagebox.showinfo, "成功", f"伤病数据更新完成，共 {len(injury_reports)} 条伤病报告")
        except Exception as e:
            error_msg = f"更新伤病数据失败: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
    
    def generate_fa_recommendations(self):
        """
        生成FA推荐
        """
        position = self.fa_position_var.get()
        risk_preference = self.fa_risk_var.get()
        top_n = int(self.fa_top_var.get())
        
        self.status_var.set(f"正在生成FA推荐... (位置: {position}, 风险: {risk_preference}, 数量: {top_n})")
        
        # 清空表格
        for item in self.fa_tree.get_children():
            self.fa_tree.delete(item)
        
        # 创建线程执行推荐
        recommend_thread = threading.Thread(target=self._generate_fa_recommendations_thread, 
                                           args=(position, risk_preference, top_n))
        recommend_thread.daemon = True
        recommend_thread.start()
    
    def _generate_fa_recommendations_thread(self, position, risk_preference, top_n):
        """
        生成FA推荐线程
        """
        try:
            from fa_analyzer.fa_analyzer import FAAnalyzer
            from fa_analyzer.recommendation import RecommendationSystem
            
            fa_analyzer = FAAnalyzer()
            recommendation_system = RecommendationSystem(fa_analyzer)
            
            # 生成推荐
            position_filter = None if position == "All" else position
            recommendations = recommendation_system.generate_recommendations(
                position=position_filter, 
                top_n=top_n, 
                risk_preference=risk_preference
            )
            
            # 更新表格
            for i, rec in enumerate(recommendations, 1):
                self.root.after(0, self.fa_tree.insert, "", tk.END, values=(
                    i,
                    rec['name'],
                    rec['team'],
                    rec['pos'],
                    f"{rec['value']['overall_value']:.2f}",
                    f"{rec['value']['statcast_score']:.2f}",
                    f"{rec['risk_adjustment']:.2f}"
                ))
            
            self.root.after(0, self.status_var.set, f"FA推荐生成完成，共 {len(recommendations)} 名球员")
            self.root.after(0, messagebox.showinfo, "成功", f"FA推荐生成完成，共 {len(recommendations)} 名球员")
        except Exception as e:
            error_msg = f"生成FA推荐失败: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
    
    def on_fa_player_select(self, event):
        """
        当选择FA球员时显示详情
        """
        selected_items = self.fa_tree.selection()
        if not selected_items:
            return
        
        item = selected_items[0]
        values = self.fa_tree.item(item, "values")
        if not values:
            return
        
        player_name = values[1]
        self.status_var.set(f"正在获取球员 {player_name} 的详情...")
        
        # 创建线程获取详情
        detail_thread = threading.Thread(target=self._get_fa_player_detail_thread, args=(player_name,))
        detail_thread.daemon = True
        detail_thread.start()
    
    def _get_fa_player_detail_thread(self, player_name):
        """
        获取FA球员详情线程
        """
        try:
            from fa_analyzer.fa_analyzer import FAAnalyzer
            
            fa_analyzer = FAAnalyzer()
            # 这里简化处理，实际应该根据player_id获取详情
            # 暂时使用模拟数据
            detail_text = f"球员: {player_name}\n"
            detail_text += "\n基本信息:\n"
            detail_text += "- 球队: Test Team\n"
            detail_text += "- 位置: OF\n"
            detail_text += "- 状态: 健康\n"
            detail_text += "\n统计数据:\n"
            detail_text += "- AVG: 0.275\n"
            detail_text += "- HR: 15\n"
            detail_text += "- RBI: 50\n"
            detail_text += "- R: 60\n"
            detail_text += "- SB: 10\n"
            detail_text += "\nStatcast数据:\n"
            detail_text += "- 出口速度: 90.5 mph\n"
            detail_text += "- 硬接触率: 35%\n"
            detail_text += "- Barrel率: 10%\n"
            detail_text += "- xwOBA: 0.340\n"
            detail_text += "\n价值评估:\n"
            detail_text += "- 综合价值: 85.5\n"
            detail_text += "- 基础分数: 75.0\n"
            detail_text += "- Statcast评分: 90.0\n"
            detail_text += "- 风险调整: 1.0\n"
            
            self.root.after(0, self.fa_detail_text.delete, 1.0, tk.END)
            self.root.after(0, self.fa_detail_text.insert, tk.END, detail_text)
            self.root.after(0, self.status_var.set, "就绪")
        except Exception as e:
            error_msg = f"获取球员详情失败: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.status_var.set, "错误")
    
    def export_fa_recommendations(self):
        """
        导出FA推荐结果
        """
        try:
            from fa_analyzer.fa_analyzer import FAAnalyzer
            from fa_analyzer.recommendation import RecommendationSystem
            
            fa_analyzer = FAAnalyzer()
            recommendation_system = RecommendationSystem(fa_analyzer)
            
            # 获取推荐数据
            position = self.fa_position_var.get()
            risk_preference = self.fa_risk_var.get()
            top_n = int(self.fa_top_var.get())
            
            position_filter = None if position == "All" else position
            recommendations = recommendation_system.generate_recommendations(
                position=position_filter, 
                top_n=top_n, 
                risk_preference=risk_preference
            )
            
            # 导出到文件
            import os
            if not os.path.exists('reports'):
                os.makedirs('reports')
            
            output_file = f"reports/fa_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            success = recommendation_system.export_recommendations(recommendations, output_file)
            
            if success:
                self.status_var.set(f"推荐结果导出成功: {output_file}")
                messagebox.showinfo("成功", f"推荐结果导出成功: {output_file}")
            else:
                self.status_var.set("导出失败")
                messagebox.showerror("错误", "导出推荐结果失败")
        except Exception as e:
            error_msg = f"导出推荐结果失败: {str(e)}"
            logger.error(error_msg)
            self.status_var.set("错误")
            messagebox.showerror("错误", error_msg)
    
    def create_help_tab(self):
        """
        创建帮助选项卡
        """
        help_tab = ttk.Frame(self.notebook)
        self.notebook.add(help_tab, text="帮助")
        
        help_frame = ttk.Frame(help_tab, padding="20")
        help_frame.pack(fill=tk.BOTH, expand=True)
        
        # 常见问题
        faq_frame = ttk.LabelFrame(help_frame, text="常见问题", padding="10")
        faq_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        faqs = [
            "Q: 如何导入数据？",
            "A: 在数据管理选项卡中选择CSV文件，然后点击导入数据按钮。",
            "",
            "Q: 如何配置联盟规则？",
            "A: 在配置设置选项卡中调整联盟规模、阵容槽位等参数，然后点击保存配置按钮。",
            "",
            "Q: 如何运行选秀模拟？",
            "A: 在选秀模拟选项卡中设置选秀顺位和策略，然后点击模拟选秀按钮。",
            "",
            "Q: 如何验证阵容？",
            "A: 在阵容验证选项卡中选择选秀日志文件，然后点击验证阵容按钮。",
            "",
            "Q: 如何查看分析结果？",
            "A: 在分析流水线选项卡中运行分析步骤，然后在排名结果中查看生成的排名文件。",
            "",
            "Q: 如何使用Statcast数据？",
            "A: 在Statcast分析选项卡中获取数据并搜索球员进行分析。",
            "",
            "Q: 如何分析伤病风险？",
            "A: 在伤病风险选项卡中输入球员ID进行风险评估。",
            "",
            "Q: 如何管理插件？",
            "A: 在插件管理选项卡中查看、启用和禁用插件。",
            "",
            "Q: 如何使用FA分析功能？",
            "A: 在FA分析选项卡中更新数据、设置筛选条件，然后点击生成推荐按钮。"
        ]
        
        for faq in faqs:
            faq_label = ttk.Label(faq_frame, text=faq, font=("Arial", 10), justify=tk.LEFT)
            faq_label.pack(anchor=tk.W, pady=2)
        
        # 联系信息
        contact_frame = ttk.LabelFrame(help_frame, text="联系信息", padding="10")
        contact_frame.pack(fill=tk.X, pady=10)
        
        contact_info = "Fantasy Baseball Pro v2026.0\n"
        contact_info += "专业级Fantasy Baseball分析与选秀模拟系统\n"
        contact_info += "© 2026 Fantasy Baseball Pro"
        
        contact_label = ttk.Label(contact_frame, text=contact_info, font=("Arial", 10))
        contact_label.pack(anchor=tk.W)
    
    def browse_pos_file(self):
        """
        浏览位置映射文件
        """
        filename = filedialog.askopenfilename(
            title="选择位置映射文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.pos_file_var.set(filename)
    
    def browse_hitters_file(self):
        """
        浏览打者数据文件
        """
        filename = filedialog.askopenfilename(
            title="选择打者数据文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.hitters_file_var.set(filename)
    
    def browse_pitchers_file(self):
        """
        浏览投手数据文件
        """
        filename = filedialog.askopenfilename(
            title="选择投手数据文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.pitchers_file_var.set(filename)
    
    def browse_roster_log(self):
        """
        浏览选秀日志文件
        """
        filename = filedialog.askopenfilename(
            title="选择选秀日志文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.roster_log_var.set(filename)
    
    def import_data(self):
        """
        导入数据
        """
        self.status_var.set("正在导入数据...")
        self.import_log.delete(1.0, tk.END)
        
        # 创建线程执行导入
        import_thread = threading.Thread(target=self._import_data_thread)
        import_thread.daemon = True
        import_thread.start()
    
    def _import_data_thread(self):
        """
        导入数据线程
        """
        try:
            # 执行导入命令
            cmd = [sys.executable, "ingest_manual_csv_to_db.py"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.import_log.insert, tk.END, line)
                self.root.after(0, self.import_log.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "数据导入成功")
                self.root.after(0, messagebox.showinfo, "成功", "数据导入成功！")
            else:
                self.root.after(0, self.status_var.set, "数据导入失败")
                self.root.after(0, messagebox.showerror, "错误", "数据导入失败，请查看日志了解详情。")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"导入数据时出错: {str(e)}")
    
    def generate_rankings(self):
        """
        生成排名
        """
        self.status_var.set("正在生成排名...")
        
        # 创建线程执行生成
        rankings_thread = threading.Thread(target=self._generate_rankings_thread)
        rankings_thread.daemon = True
        rankings_thread.start()
    
    def _generate_rankings_thread(self):
        """
        生成排名线程
        """
        try:
            # 执行生成命令
            cmd = [sys.executable, "fantasy_scoring_model_v2.py"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            output = process.communicate()[0]
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "排名生成成功")
                self.root.after(0, self.refresh_rankings)
                self.root.after(0, messagebox.showinfo, "成功", "排名生成成功！")
            else:
                self.root.after(0, self.status_var.set, "排名生成失败")
                self.root.after(0, messagebox.showerror, "错误", f"排名生成失败: {output}")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"生成排名时出错: {str(e)}")
    
    def fetch_adp(self):
        """
        获取ADP
        """
        self.status_var.set("正在获取ADP...")
        
        # 创建线程执行获取
        adp_thread = threading.Thread(target=self._fetch_adp_thread)
        adp_thread.daemon = True
        adp_thread.start()
    
    def _fetch_adp_thread(self):
        """
        获取ADP线程
        """
        try:
            # 执行获取命令
            cmd = [sys.executable, "fetch_adp_cached.py", "--force"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            output = process.communicate()[0]
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "ADP获取成功")
                self.root.after(0, messagebox.showinfo, "成功", "ADP获取成功！")
            else:
                self.root.after(0, self.status_var.set, "ADP获取失败")
                self.root.after(0, messagebox.showerror, "错误", f"ADP获取失败: {output}")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"获取ADP时出错: {str(e)}")
    
    def validate_data_quality(self):
        """
        运行数据质量校验
        """
        self.status_var.set("正在运行数据质量校验...")
        
        # 创建线程执行校验
        validate_thread = threading.Thread(target=self._validate_data_quality_thread)
        validate_thread.daemon = True
        validate_thread.start()
    
    def _validate_data_quality_thread(self):
        """
        运行数据质量校验线程
        """
        try:
            # 执行数据质量校验命令
            cmd = [sys.executable, "validate_data_quality.py"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            output = process.communicate()[0]
            process.wait()
            
            if process.returncode == 0:
                # 检查是否生成了验证报告
                report_file = "data_quality_report.txt"
                if os.path.exists(report_file):
                    with open(report_file, 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    
                    # 显示报告
                    self.root.after(0, self.show_report_window, "数据质量验证报告", report_content)
                    self.root.after(0, self.status_var.set, "数据质量校验完成")
                    logger.info("数据质量校验完成并显示报告")
                else:
                    # 显示命令输出
                    self.root.after(0, self.show_report_window, "数据质量校验结果", output)
                    self.root.after(0, self.status_var.set, "数据质量校验完成")
            else:
                self.root.after(0, self.status_var.set, "数据质量校验失败")
                self.root.after(0, messagebox.showerror, "错误", f"数据质量校验失败: {output}")
                logger.error(f"数据质量校验失败: {output}")
        except Exception as e:
            error_msg = f"运行数据质量校验时出错: {str(e)}"
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", error_msg)
            logger.error(error_msg)
    
    def show_report_window(self, title, content):
        """
        显示报告窗口
        
        Args:
            title: 窗口标题
            content: 报告内容
        """
        # 创建报告窗口
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("800x600")
        report_window.resizable(True, True)
        
        # 创建滚动文本框
        text_frame = ttk.Frame(report_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text = tk.Text(text_frame, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        
        # 插入内容
        text.insert(tk.END, content)
        
        # 添加关闭按钮
        button_frame = ttk.Frame(report_window, padding="10")
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="关闭", command=report_window.destroy).pack(side=tk.RIGHT)
    
    def run_full_pipeline(self):
        """
        运行完整流水线
        """
        self.status_var.set("正在运行完整流水线...")
        
        # 创建线程执行流水线
        pipeline_thread = threading.Thread(target=self._run_full_pipeline_thread)
        pipeline_thread.daemon = True
        pipeline_thread.start()
    
    def _run_full_pipeline_thread(self):
        """
        运行完整流水线线程
        """
        try:
            # 步骤1: 导入数据
            self.root.after(0, self.status_var.set, "正在导入数据...")
            cmd1 = [sys.executable, "ingest_manual_csv_to_db.py"]
            process1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output1 = process1.communicate()[0]
            
            if process1.returncode != 0:
                self.root.after(0, self.status_var.set, "流水线执行失败")
                self.root.after(0, messagebox.showerror, "错误", f"数据导入失败: {output1}")
                return
            
            # 步骤2: 数据质量校验
            self.root.after(0, self.status_var.set, "正在运行数据质量校验...")
            cmd2 = [sys.executable, "validate_data_quality.py"]
            process2 = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output2 = process2.communicate()[0]
            
            if process2.returncode != 0:
                self.root.after(0, self.status_var.set, "流水线执行失败")
                self.root.after(0, messagebox.showerror, "错误", f"数据质量校验失败: {output2}")
                return
            
            # 步骤3: 生成排名
            self.root.after(0, self.status_var.set, "正在生成排名...")
            cmd3 = [sys.executable, "fantasy_scoring_model_v2.py"]
            process3 = subprocess.Popen(cmd3, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output3 = process3.communicate()[0]
            
            if process3.returncode != 0:
                self.root.after(0, self.status_var.set, "流水线执行失败")
                self.root.after(0, messagebox.showerror, "错误", f"排名生成失败: {output3}")
                return
            
            # 步骤4: 获取ADP
            self.root.after(0, self.status_var.set, "正在获取ADP...")
            cmd4 = [sys.executable, "fetch_adp_cached.py"]
            process4 = subprocess.Popen(cmd4, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output4 = process4.communicate()[0]
            
            self.root.after(0, self.status_var.set, "流水线执行成功")
            self.root.after(0, self.refresh_rankings)
            self.root.after(0, messagebox.showinfo, "成功", "完整流水线执行成功！")
            
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"运行流水线时出错: {str(e)}")
    
    def simulate_draft(self):
        """
        模拟选秀
        """
        pick = self.draft_pick_var.get()
        strategy = self.draft_strategy_var.get()
        
        self.status_var.set(f"正在模拟选秀... (顺位: {pick}, 策略: {strategy})")
        self.draft_log.delete(1.0, tk.END)
        
        # 创建线程执行模拟
        draft_thread = threading.Thread(target=self._simulate_draft_thread, args=(pick, strategy))
        draft_thread.daemon = True
        draft_thread.start()
    
    def _simulate_draft_thread(self, pick, strategy):
        """
        模拟选秀线程
        """
        try:
            # 执行模拟命令
            cmd = [sys.executable, "snake_draft_simulator_pro.py", "--pick", pick]
            if strategy:
                cmd.extend(["--strategy", strategy])
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.draft_log.insert, tk.END, line)
                self.root.after(0, self.draft_log.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "选秀模拟成功")
                self.root.after(0, messagebox.showinfo, "成功", "选秀模拟成功！")
            else:
                self.root.after(0, self.status_var.set, "选秀模拟失败")
                self.root.after(0, messagebox.showerror, "错误", "选秀模拟失败，请查看日志了解详情。")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"模拟选秀时出错: {str(e)}")
    
    def validate_roster(self):
        """
        验证阵容
        """
        log_file = self.roster_log_var.get()
        
        self.status_var.set("正在验证阵容...")
        self.roster_result.delete(1.0, tk.END)
        
        # 创建线程执行验证
        validate_thread = threading.Thread(target=self._validate_roster_thread, args=(log_file,))
        validate_thread.daemon = True
        validate_thread.start()
    
    def _validate_roster_thread(self, log_file):
        """
        验证阵容线程
        """
        try:
            # 执行验证命令
            cmd = [sys.executable, "validate_roster.py", log_file]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.roster_result.insert, tk.END, line)
                self.root.after(0, self.roster_result.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "阵容验证完成")
            else:
                self.root.after(0, self.status_var.set, "阵容验证失败")
                self.root.after(0, messagebox.showerror, "错误", "阵容验证失败，请查看结果了解详情。")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"验证阵容时出错: {str(e)}")
    
    def save_config(self):
        """
        保存配置
        """
        try:
            # 读取当前配置
            import yaml
            with open("config.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            # 更新配置
            config["league"]["size"] = int(self.league_size_var.get())
            config["league"]["rounds"] = int(self.league_rounds_var.get())
            
            # 更新阵容槽位
            for pos, var in self.roster_vars.items():
                config["league"]["roster_slots"][pos] = int(var.get())
            
            # 更新选秀策略
            config["draft_simulator"]["default_strategy"] = self.strategy_var.get()
            
            # 保存配置
            with open("config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            self.status_var.set("配置保存成功")
            messagebox.showinfo("成功", "配置保存成功！")
        except Exception as e:
            self.status_var.set("配置保存失败")
            messagebox.showerror("错误", f"保存配置时出错: {str(e)}")
    
    def refresh_rankings(self):
        """
        刷新排名列表
        """
        self.rankings_list.delete(0, tk.END)
        
        # 查找排名文件
        for file in os.listdir("."):
            if file.startswith("fantasy_draft_rankings") and file.endswith(".csv"):
                self.rankings_list.insert(tk.END, file)
    
    def fetch_statcast_data(self):
        """
        获取Statcast数据
        """
        self.status_var.set("正在获取Statcast数据...")
        self.statcast_data_text.delete(1.0, tk.END)
        
        # 创建线程执行获取
        statcast_thread = threading.Thread(target=self._fetch_statcast_data_thread)
        statcast_thread.daemon = True
        statcast_thread.start()
    
    def _fetch_statcast_data_thread(self):
        """
        获取Statcast数据线程
        """
        try:
            # 执行获取命令
            cmd = [sys.executable, "data/statcast_data.py"]
            if self.statcast_update_var.get():
                cmd.append("--update")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.statcast_data_text.insert, tk.END, line)
                self.root.after(0, self.statcast_data_text.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "Statcast数据获取成功")
                self.root.after(0, messagebox.showinfo, "成功", "Statcast数据获取成功！")
            else:
                self.root.after(0, self.status_var.set, "Statcast数据获取失败")
                self.root.after(0, messagebox.showerror, "错误", "Statcast数据获取失败，请查看日志了解详情。")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"获取Statcast数据时出错: {str(e)}")
    
    def search_player_statcast(self):
        """
        搜索球员Statcast数据
        """
        player_name = self.player_search_var.get()
        if not player_name:
            messagebox.showwarning("警告", "请输入球员姓名")
            return
        
        self.status_var.set(f"正在搜索球员: {player_name}...")
        self.statcast_data_text.delete(1.0, tk.END)
        
        # 创建线程执行搜索
        search_thread = threading.Thread(target=self._search_player_statcast_thread, args=(player_name,))
        search_thread.daemon = True
        search_thread.start()
    
    def _search_player_statcast_thread(self, player_name):
        """
        搜索球员Statcast数据线程
        """
        try:
            # 执行搜索命令
            cmd = [sys.executable, "data/statcast_data.py", "--search", player_name]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.statcast_data_text.insert, tk.END, line)
                self.root.after(0, self.statcast_data_text.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "球员搜索完成")
            else:
                self.root.after(0, self.status_var.set, "球员搜索失败")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"搜索球员时出错: {str(e)}")
    
    def update_injury_data(self):
        """
        更新伤病数据
        """
        self.status_var.set("正在更新伤病数据...")
        self.injury_result_text.delete(1.0, tk.END)
        
        # 创建线程执行更新
        injury_thread = threading.Thread(target=self._update_injury_data_thread)
        injury_thread.daemon = True
        injury_thread.start()
    
    def _update_injury_data_thread(self):
        """
        更新伤病数据线程
        """
        try:
            # 执行更新命令
            cmd = [sys.executable, "data/injury_data.py", "--update"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.injury_result_text.insert, tk.END, line)
                self.root.after(0, self.injury_result_text.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "伤病数据更新成功")
                self.root.after(0, messagebox.showinfo, "成功", "伤病数据更新成功！")
            else:
                self.root.after(0, self.status_var.set, "伤病数据更新失败")
                self.root.after(0, messagebox.showerror, "错误", "伤病数据更新失败，请查看日志了解详情。")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"更新伤病数据时出错: {str(e)}")
    
    def analyze_injury_risk(self):
        """
        分析球员伤病风险
        """
        player_id = self.player_id_var.get()
        if not player_id:
            messagebox.showwarning("警告", "请输入球员ID")
            return
        
        self.status_var.set(f"正在分析球员伤病风险: {player_id}...")
        self.injury_result_text.delete(1.0, tk.END)
        
        # 创建线程执行分析
        risk_thread = threading.Thread(target=self._analyze_injury_risk_thread, args=(player_id,))
        risk_thread.daemon = True
        risk_thread.start()
    
    def _analyze_injury_risk_thread(self, player_id):
        """
        分析球员伤病风险线程
        """
        try:
            # 执行分析命令
            cmd = [sys.executable, "data/injury_data.py", "--analyze", player_id]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # 读取输出
            for line in process.stdout:
                self.root.after(0, self.injury_result_text.insert, tk.END, line)
                self.root.after(0, self.injury_result_text.see, tk.END)
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.status_var.set, "伤病风险分析完成")
            else:
                self.root.after(0, self.status_var.set, "伤病风险分析失败")
        except Exception as e:
            self.root.after(0, self.status_var.set, "错误")
            self.root.after(0, messagebox.showerror, "错误", f"分析伤病风险时出错: {str(e)}")
    
    def refresh_plugins(self):
        """
        刷新插件列表
        """
        self.status_var.set("正在刷新插件列表...")
        self.plugin_list.delete(0, tk.END)
        self.plugin_config_text.delete(1.0, tk.END)
        
        try:
            # 执行插件列表命令
            cmd = [sys.executable, "-c", "from plugins.plugin_manager import PluginManager; pm = PluginManager(); print('\n'.join([p.name + ' - ' + ('启用' if p.enabled else '禁用') for p in pm.plugins]))"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = process.communicate()[0]
            
            if process.returncode == 0:
                for line in output.strip().split('\n'):
                    if line:
                        self.plugin_list.insert(tk.END, line)
                self.status_var.set("插件列表刷新成功")
            else:
                self.status_var.set("插件列表刷新失败")
                self.plugin_config_text.insert(tk.END, f"错误: {output}")
        except Exception as e:
            self.status_var.set("错误")
            self.plugin_config_text.insert(tk.END, f"获取插件列表时出错: {str(e)}")
    
    def enable_plugin(self):
        """
        启用插件
        """
        selected = self.plugin_list.curselection()
        if not selected:
            messagebox.showwarning("警告", "请选择一个插件")
            return
        
        plugin_info = self.plugin_list.get(selected[0])
        plugin_name = plugin_info.split(' - ')[0]
        
        self.status_var.set(f"正在启用插件: {plugin_name}...")
        
        try:
            # 执行启用命令
            cmd = [sys.executable, "-c", f"from plugins.plugin_manager import PluginManager; pm = PluginManager(); pm.enable_plugin('{plugin_name}'); pm.save_config()"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = process.communicate()[0]
            
            if process.returncode == 0:
                self.status_var.set(f"插件 {plugin_name} 启用成功")
                self.refresh_plugins()
                messagebox.showinfo("成功", f"插件 {plugin_name} 启用成功！")
            else:
                self.status_var.set(f"插件 {plugin_name} 启用失败")
                messagebox.showerror("错误", f"启用插件失败: {output}")
        except Exception as e:
            self.status_var.set("错误")
            messagebox.showerror("错误", f"启用插件时出错: {str(e)}")
    
    def disable_plugin(self):
        """
        禁用插件
        """
        selected = self.plugin_list.curselection()
        if not selected:
            messagebox.showwarning("警告", "请选择一个插件")
            return
        
        plugin_info = self.plugin_list.get(selected[0])
        plugin_name = plugin_info.split(' - ')[0]
        
        self.status_var.set(f"正在禁用插件: {plugin_name}...")
        
        try:
            # 执行禁用命令
            cmd = [sys.executable, "-c", f"from plugins.plugin_manager import PluginManager; pm = PluginManager(); pm.disable_plugin('{plugin_name}'); pm.save_config()"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = process.communicate()[0]
            
            if process.returncode == 0:
                self.status_var.set(f"插件 {plugin_name} 禁用成功")
                self.refresh_plugins()
                messagebox.showinfo("成功", f"插件 {plugin_name} 禁用成功！")
            else:
                self.status_var.set(f"插件 {plugin_name} 禁用失败")
                messagebox.showerror("错误", f"禁用插件失败: {output}")
        except Exception as e:
            self.status_var.set("错误")
            messagebox.showerror("错误", f"禁用插件时出错: {str(e)}")
    
    def process_commands(self):
        """
        处理命令队列
        """
        while True:
            try:
                cmd = self.cmd_queue.get(block=True, timeout=1)
                cmd()
                self.cmd_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print(f"处理命令时出错: {str(e)}")


if __name__ == "__main__":
    # 创建根窗口
    root = tk.Tk()
    
    # 设置样式
    style = ttk.Style()
    style.configure("Accent.TButton", foreground="white", background="#0078d7")
    
    # 创建应用
    app = FantasyBaseballGUI(root)
    
    # 运行主循环
    root.mainloop()
