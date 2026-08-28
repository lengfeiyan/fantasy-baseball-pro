#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试FA分析引擎
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fa_analyzer.fa_analyzer import FAAnalyzer
from fa_analyzer.recommendation import RecommendationSystem
from utils.logger import get_logger

logger = get_logger('test_fa_analyzer')

def test_fa_analyzer():
    """测试FA分析引擎"""
    try:
        logger.info("开始测试FA分析引擎...")
        
        # 创建FA分析引擎
        fa_analyzer = FAAnalyzer()
        
        # 测试获取FA池
        logger.info("测试获取FA池...")
        fa_pool = fa_analyzer.get_fa_pool()
        logger.info(f"FA池共有 {len(fa_pool)} 名球员")
        
        # 测试计算球员价值
        if fa_pool:
            logger.info("测试计算球员价值...")
            for player in fa_pool[:3]:  # 测试前3名球员
                value = fa_analyzer.calculate_fa_value(player['player_id'])
                logger.info(f"球员 {player['name']} 的价值: {value['overall_value']:.2f}")
        
        # 测试推荐系统
        logger.info("测试推荐系统...")
        recommendation_system = RecommendationSystem(fa_analyzer)
        
        # 生成推荐
        recommendations = recommendation_system.generate_recommendations(top_n=5)
        logger.info(f"生成了 {len(recommendations)} 个推荐")
        
        # 显示推荐结果
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"推荐 #{i}: {rec['name']} ({rec['pos']}) - 价值: {rec['final_score']:.2f}")
        
        # 测试位置推荐
        logger.info("测试位置推荐...")
        of_recommendations = recommendation_system.get_position_recommendations('OF', top_n=3)
        logger.info(f"OF位置推荐: {len(of_recommendations)} 个")
        
        logger.info("FA分析引擎测试完成！")
        return True
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == '__main__':
    test_fa_analyzer()
