#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FA数据导入工具
支持在线数据获取和手工文件导入
"""

import os
import argparse
import json
from datetime import datetime

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fa_analyzer.real_time_data import RealTimeData
from utils.logger import get_logger
logger = get_logger('import_fa_data')

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='FA数据导入工具')
    parser.add_argument('--action', choices=['update-fa', 'update-injury', 'import-file'], required=True,
                        help='操作类型: update-fa (更新FA池), update-injury (更新伤病数据), import-file (导入文件)')
    parser.add_argument('--file', help='导入文件路径')
    parser.add_argument('--type', choices=['fa_pool', 'player_stats', 'injury_reports'],
                        help='导入文件类型')
    parser.add_argument('--db', default='fantasy_baseball.db', help='数据库文件路径')
    
    args = parser.parse_args()
    
    try:
        rtd = RealTimeData(args.db)
        
        if args.action == 'update-fa':
            logger.info("开始更新FA池数据...")
            fa_players = rtd.update_fa_pool()
            logger.info(f"FA池更新完成，共 {len(fa_players)} 名球员")
            print(f"✅ FA池更新完成，共 {len(fa_players)} 名球员")
            
        elif args.action == 'update-injury':
            logger.info("开始更新伤病数据...")
            injury_reports = rtd.update_injury_data()
            logger.info(f"伤病数据更新完成，共 {len(injury_reports)} 条伤病报告")
            print(f"✅ 伤病数据更新完成，共 {len(injury_reports)} 条伤病报告")
            
        elif args.action == 'import-file':
            if not args.file:
                parser.error("--file 参数是必需的")
            if not args.type:
                parser.error("--type 参数是必需的")
            
            if not os.path.exists(args.file):
                logger.error(f"文件不存在: {args.file}")
                print(f"❌ 文件不存在: {args.file}")
                return
            
            logger.info(f"开始从文件导入 {args.type} 数据: {args.file}")
            count = rtd.import_data_from_file(args.file, args.type)
            logger.info(f"文件导入完成，共 {count} 条记录")
            print(f"✅ 文件导入完成，共 {count} 条记录")
            
    except Exception as e:
        logger.error(f"操作失败: {str(e)}")
        print(f"❌ 操作失败: {str(e)}")

if __name__ == '__main__':
    main()
