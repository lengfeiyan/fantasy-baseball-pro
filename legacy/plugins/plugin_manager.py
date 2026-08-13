#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件管理器
负责加载、注册和管理所有插件
"""

import os
import importlib.util
import sys
from typing import Dict, List, Optional, Any
from .base_plugin import BasePlugin


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugins_dir: str = 'plugins'):
        """
        初始化插件管理器
        
        Args:
            plugins_dir: 插件目录路径
        """
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, BasePlugin] = {}
        self.enabled_plugins: List[str] = []
    
    def load_plugins(self) -> List[str]:
        """
        加载所有插件
        
        Returns:
            List[str]: 加载成功的插件名称列表
        """
        loaded_plugins = []
        
        # 确保插件目录存在
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
        
        # 遍历插件目录
        for item in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, item)
            
            # 跳过__pycache__和非目录项
            if item == '__pycache__' or not os.path.isdir(plugin_path):
                continue
            
            # 检查插件目录是否包含__init__.py
            init_file = os.path.join(plugin_path, '__init__.py')
            if not os.path.exists(init_file):
                continue
            
            # 尝试导入插件
            try:
                # 添加插件目录到Python路径
                sys.path.insert(0, self.plugins_dir)
                
                # 导入插件模块
                plugin_name = item
                module_spec = importlib.util.spec_from_file_location(plugin_name, init_file)
                if module_spec and module_spec.loader:
                    module = importlib.util.module_from_spec(module_spec)
                    sys.modules[plugin_name] = module
                    module_spec.loader.exec_module(module)
                    
                    # 查找插件类
                    for name in dir(module):
                        obj = getattr(module, name)
                        if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj != BasePlugin:
                            # 实例化插件
                            plugin = obj()
                            if plugin.initialize():
                                self.plugins[plugin_name] = plugin
                                loaded_plugins.append(plugin_name)
                                print(f"✅ 成功加载插件: {plugin_name}")
                            else:
                                print(f"❌ 插件初始化失败: {plugin_name}")
                            break
            except Exception as e:
                print(f"❌ 加载插件 {item} 失败: {e}")
            finally:
                # 从Python路径中移除插件目录
                if self.plugins_dir in sys.path:
                    sys.path.remove(self.plugins_dir)
        
        return loaded_plugins
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        获取指定插件
        
        Args:
            name: 插件名称
            
        Returns:
            Optional[BasePlugin]: 插件实例
        """
        return self.plugins.get(name)
    
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """
        注册新插件
        
        Args:
            plugin: 插件实例
            
        Returns:
            bool: 注册是否成功
        """
        try:
            if plugin.initialize():
                self.plugins[plugin.name] = plugin
                return True
            return False
        except Exception:
            return False
    
    def enable_plugin(self, name: str) -> bool:
        """
        启用插件
        
        Args:
            name: 插件名称
            
        Returns:
            bool: 启用是否成功
        """
        if name in self.plugins and name not in self.enabled_plugins:
            self.enabled_plugins.append(name)
            return True
        return False
    
    def disable_plugin(self, name: str) -> bool:
        """
        禁用插件
        
        Args:
            name: 插件名称
            
        Returns:
            bool: 禁用是否成功
        """
        if name in self.enabled_plugins:
            self.enabled_plugins.remove(name)
            return True
        return False
    
    def get_enabled_plugins(self) -> List[str]:
        """
        获取已启用的插件
        
        Returns:
            List[str]: 已启用的插件名称列表
        """
        return self.enabled_plugins.copy()
    
    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """
        获取所有插件
        
        Returns:
            Dict[str, BasePlugin]: 插件名称到插件实例的映射
        """
        return self.plugins.copy()
    
    def shutdown(self) -> None:
        """
        关闭所有插件
        """
        for plugin_name, plugin in self.plugins.items():
            try:
                plugin.shutdown()
                print(f"✅ 成功关闭插件: {plugin_name}")
            except Exception as e:
                print(f"❌ 关闭插件 {plugin_name} 失败: {e}")
