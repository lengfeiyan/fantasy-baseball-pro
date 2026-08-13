#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件基类
所有自定义插件必须继承此类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BasePlugin(ABC):
    """插件基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化插件
        
        Args:
            config: 插件配置
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        self.version = getattr(self, 'VERSION', '1.0.0')
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """
        关闭插件
        
        Returns:
            bool: 关闭是否成功
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取插件信息
        
        Returns:
            Dict[str, Any]: 插件信息
        """
        return {
            'name': self.name,
            'version': self.version,
            'description': getattr(self, 'DESCRIPTION', 'No description provided')
        }
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """
        配置插件
        
        Args:
            config: 插件配置
            
        Returns:
            bool: 配置是否成功
        """
        try:
            self.config.update(config)
            return True
        except Exception:
            return False
