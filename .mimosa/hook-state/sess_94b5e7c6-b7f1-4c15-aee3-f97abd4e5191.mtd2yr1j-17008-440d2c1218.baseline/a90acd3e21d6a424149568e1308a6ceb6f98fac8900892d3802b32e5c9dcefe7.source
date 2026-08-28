#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量检测工具
用于检测手工下载的数据是否符合要求，包括字段是否齐全、字段名是否准确等
"""

import os
import pandas as pd
from typing import Dict, List, Tuple
from config_loader import get_config

# 添加日志功能
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import get_logger
logger = get_logger('data_quality')


class DataQualityValidator:
    """数据质量验证器类"""
    
    def __init__(self):
        """
        初始化数据质量验证器
        """
        self.config = get_config()
        self.hitter_required_columns = {
            'Name': '球员姓名',
            'Team': '球队',
            'POS': '位置',
            'R': '得分',
            'HR': '本垒打',
            'RBI': '打点',
            'SB': '盗垒',
            'AVG': '打击率',
            'OBP': '上垒率',
            'SLG': '长打率',
            'OPS': '上垒加长打率',
            'PA': '打席数'
        }
        
        self.pitcher_required_columns = {
            'Name': '球员姓名',
            'Team': '球队',
            'POS': '位置',
            'W': '胜场',
            'L': '败场',
            'SV': '救援成功',
            'HOLD': '中继成功',
            'ERA': '自责分率',
            'WHIP': '每局被上垒率',
            'K/9': '每9局三振数',
            'BB/9': '每9局保送数',
            'IP': '投球局数'
        }
    
    def validate_file_exists(self, file_path: str) -> bool:
        """
        验证文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 文件是否存在
        """
        if os.path.exists(file_path):
            logger.info(f"文件存在: {file_path}")
            return True
        else:
            logger.error(f"文件不存在: {file_path}")
            return False
    
    def validate_hitter_data(self, file_path: str) -> Dict:
        """
        验证打者数据质量
        
        Args:
            file_path: 打者数据文件路径
            
        Returns:
            Dict: 验证结果
        """
        logger.info(f"开始验证打者数据: {file_path}")
        result = {
            'file': file_path,
            'type': 'hitters',
            'valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        try:
            # 读取文件
            df = pd.read_csv(file_path)
            result['statistics']['total_rows'] = len(df)
            logger.info(f"成功读取文件，共 {len(df)} 行数据")
            
            # 清理列名
            df.columns = [col.strip() for col in df.columns]
            logger.info(f"文件包含列: {list(df.columns)}")
            
            # 验证必需字段
            missing_columns = []
            for col, desc in self.hitter_required_columns.items():
                if col not in df.columns:
                    missing_columns.append(f"{col} ({desc})")
            
            if missing_columns:
                error_msg = f"缺少必需字段: {missing_columns}"
                result['errors'].append(error_msg)
                logger.error(error_msg)
                result['valid'] = False
            else:
                logger.info("所有必需字段都存在")
            
            # 验证数据质量
            # 检查姓名字段是否为空
            if 'Name' in df.columns:
                name_null_count = df['Name'].isnull().sum()
                if name_null_count > 0:
                    warning_msg = f"有 {name_null_count} 行数据的球员姓名为空"
                    result['warnings'].append(warning_msg)
                    logger.warning(warning_msg)
            
            # 检查数值字段
            numeric_columns = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG', 'OPS', 'PA']
            for col in numeric_columns:
                if col in df.columns:
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        warning_msg = f"字段 {col} 有 {null_count} 个缺失值"
                        result['warnings'].append(warning_msg)
                        logger.warning(warning_msg)
            
            # 检查数据类型
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        pd.to_numeric(df[col])
                    except Exception:
                        error_msg = f"字段 {col} 包含非数值数据"
                        result['errors'].append(error_msg)
                        logger.error(error_msg)
                        result['valid'] = False
            
        except Exception as e:
            error_msg = f"验证过程出错: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)
            result['valid'] = False
        
        logger.info(f"打者数据验证完成，结果: {'有效' if result['valid'] else '无效'}")
        return result
    
    def validate_pitcher_data(self, file_path: str) -> Dict:
        """
        验证投手数据质量
        
        Args:
            file_path: 投手数据文件路径
            
        Returns:
            Dict: 验证结果
        """
        logger.info(f"开始验证投手数据: {file_path}")
        result = {
            'file': file_path,
            'type': 'pitchers',
            'valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        try:
            # 读取文件
            df = pd.read_csv(file_path)
            result['statistics']['total_rows'] = len(df)
            logger.info(f"成功读取文件，共 {len(df)} 行数据")
            
            # 清理列名
            df.columns = [col.strip() for col in df.columns]
            logger.info(f"文件包含列: {list(df.columns)}")
            
            # 验证必需字段
            missing_columns = []
            for col, desc in self.pitcher_required_columns.items():
                if col not in df.columns:
                    missing_columns.append(f"{col} ({desc})")
            
            if missing_columns:
                error_msg = f"缺少必需字段: {missing_columns}"
                result['errors'].append(error_msg)
                logger.error(error_msg)
                result['valid'] = False
            else:
                logger.info("所有必需字段都存在")
            
            # 验证数据质量
            # 检查姓名字段是否为空
            if 'Name' in df.columns:
                name_null_count = df['Name'].isnull().sum()
                if name_null_count > 0:
                    warning_msg = f"有 {name_null_count} 行数据的球员姓名为空"
                    result['warnings'].append(warning_msg)
                    logger.warning(warning_msg)
            
            # 检查数值字段
            numeric_columns = ['W', 'L', 'SV', 'HOLD', 'ERA', 'WHIP', 'K/9', 'BB/9', 'IP']
            for col in numeric_columns:
                if col in df.columns:
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        warning_msg = f"字段 {col} 有 {null_count} 个缺失值"
                        result['warnings'].append(warning_msg)
                        logger.warning(warning_msg)
            
            # 检查数据类型
            for col in numeric_columns:
                if col in df.columns:
                    try:
                        pd.to_numeric(df[col])
                    except Exception:
                        error_msg = f"字段 {col} 包含非数值数据"
                        result['errors'].append(error_msg)
                        logger.error(error_msg)
                        result['valid'] = False
            
        except Exception as e:
            error_msg = f"验证过程出错: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)
            result['valid'] = False
        
        logger.info(f"投手数据验证完成，结果: {'有效' if result['valid'] else '无效'}")
        return result
    
    def validate_all_data(self) -> List[Dict]:
        """
        验证所有数据文件
        
        Returns:
            List[Dict]: 所有文件的验证结果
        """
        logger.info("开始验证所有数据文件")
        results = []
        
        # 获取配置信息
        use_multi_source = self.config['data']['use_multi_source']
        
        if use_multi_source:
            # 多源数据验证
            sources = self.config['projections']['sources']
            hitter_pattern = self.config['data']['file_patterns']['hitters']
            pitcher_pattern = self.config['data']['file_patterns']['pitchers']
            
            for source in sources:
                # 验证打者数据
                hitter_file = os.path.join('data', hitter_pattern.format(source=source.lower()))
                if self.validate_file_exists(hitter_file):
                    result = self.validate_hitter_data(hitter_file)
                    results.append(result)
                
                # 验证投手数据
                pitcher_file = os.path.join('data', pitcher_pattern.format(source=source.lower()))
                if self.validate_file_exists(pitcher_file):
                    result = self.validate_pitcher_data(pitcher_file)
                    results.append(result)
        else:
            # 单源数据验证
            hitter_file = os.path.join('data', 'hitters_2026.csv')
            if self.validate_file_exists(hitter_file):
                result = self.validate_hitter_data(hitter_file)
                results.append(result)
            
            pitcher_file = os.path.join('data', 'pitchers_2026.csv')
            if self.validate_file_exists(pitcher_file):
                result = self.validate_pitcher_data(pitcher_file)
                results.append(result)
        
        # 验证位置映射文件
        positions_file = self.config['data']['positions_file']
        if self.validate_file_exists(positions_file):
            logger.info(f"位置映射文件存在: {positions_file}")
        
        logger.info("所有数据文件验证完成")
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """
        生成验证报告
        
        Args:
            results: 验证结果列表
            
        Returns:
            str: 验证报告
        """
        logger.info("生成验证报告")
        report = []
        report.append("=" * 80)
        report.append("Fantasy Baseball 数据质量验证报告")
        report.append("=" * 80)
        
        total_files = len(results)
        valid_files = sum(1 for r in results if r['valid'])
        invalid_files = total_files - valid_files
        
        report.append(f"总文件数: {total_files}")
        report.append(f"有效文件数: {valid_files}")
        report.append(f"无效文件数: {invalid_files}")
        report.append("" )
        
        for result in results:
            report.append("-" * 60)
            report.append(f"文件: {result['file']}")
            report.append(f"类型: {result['type']}")
            report.append(f"状态: {'✅ 有效' if result['valid'] else '❌ 无效'}")
            
            if result['statistics']:
                report.append("统计信息:")
                for key, value in result['statistics'].items():
                    report.append(f"  - {key}: {value}")
            
            if result['errors']:
                report.append("错误:")
                for error in result['errors']:
                    report.append(f"  - {error}")
            
            if result['warnings']:
                report.append("警告:")
                for warning in result['warnings']:
                    report.append(f"  - {warning}")
            
            report.append("")
        
        report.append("=" * 80)
        report.append(f"验证完成，{valid_files}/{total_files} 文件有效")
        report.append("=" * 80)
        
        report_str = "\n".join(report)
        logger.info("验证报告生成完成")
        return report_str


def main():
    """
    主函数
    """
    logger.info("=========================================")
    logger.info("开始执行数据质量验证工具")
    logger.info("=========================================")
    
    print("=== Fantasy Baseball 数据质量验证工具 ===")
    print("正在验证数据文件...\n")
    
    # 创建验证器
    validator = DataQualityValidator()
    
    try:
        # 验证所有数据
        results = validator.validate_all_data()
        
        # 生成报告
        report = validator.generate_report(results)
        
        # 打印报告
        print(report)
        
        # 保存报告到文件
        report_file = "data_quality_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"验证报告已保存到: {report_file}")
        print(f"\n验证报告已保存到: {report_file}")
        
    except Exception as e:
        error_msg = f"执行过程中出错: {str(e)}"
        logger.error(error_msg)
        print(f"\n❌ 错误: {e}")
    
    logger.info("=========================================")
    logger.info("数据质量验证工具执行完成")
    logger.info("=========================================")


if __name__ == '__main__':
    main()