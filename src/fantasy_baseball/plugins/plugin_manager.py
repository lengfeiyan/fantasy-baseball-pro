"""插件管理器：加载、注册、启用/禁用插件。

迁移自旧版，plugins_dir 基于项目根解析。用 logger 替代 print。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Dict, List, Optional

from ..config import PROJECT_ROOT
from ..utils.logger import get_logger
from .base_plugin import BasePlugin

logger = get_logger("plugins")


class PluginManager:
    """插件管理器。"""

    def __init__(self, plugins_dir: Optional[str] = None):
        self.plugins_dir = plugins_dir or os.path.join(PROJECT_ROOT, "plugins")
        self.plugins: Dict[str, BasePlugin] = {}
        self.enabled_plugins: List[str] = []

    def load_plugins(self) -> List[str]:
        """加载所有插件，返回成功加载的插件名列表。"""
        loaded: List[str] = []
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            return loaded

        for item in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, item)
            if item == "__pycache__" or not os.path.isdir(plugin_path):
                continue
            init_file = os.path.join(plugin_path, "__init__.py")
            if not os.path.exists(init_file):
                continue
            try:
                sys.path.insert(0, self.plugins_dir)
                spec = importlib.util.spec_from_file_location(item, init_file)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                # 注册名加前缀：插件目录名与标准库/三方包同名时（如 json），
                # 直接用裸名注册会进程级劫持后续所有同名 import
                sys.modules[f"_fb_plugin_{item}"] = module
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    obj = getattr(module, attr_name)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, BasePlugin)
                        and obj is not BasePlugin
                    ):
                        plugin = obj()
                        if plugin.initialize():
                            self.plugins[item] = plugin
                            loaded.append(item)
                            logger.info("加载插件成功: %s", item)
                        else:
                            logger.warning("插件初始化失败: %s", item)
                        break
            except Exception as e:
                logger.warning("加载插件 %s 失败: %s", item, e)
            finally:
                if self.plugins_dir in sys.path:
                    sys.path.remove(self.plugins_dir)
        return loaded

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self.plugins.get(name)

    def register_plugin(self, plugin: BasePlugin) -> bool:
        try:
            if plugin.initialize():
                self.plugins[plugin.name] = plugin
                return True
            return False
        except Exception:
            return False

    def enable_plugin(self, name: str) -> bool:
        if name in self.plugins and name not in self.enabled_plugins:
            self.enabled_plugins.append(name)
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        if name in self.enabled_plugins:
            self.enabled_plugins.remove(name)
            return True
        return False

    def get_enabled_plugins(self) -> List[str]:
        return list(self.enabled_plugins)

    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        return dict(self.plugins)

    def shutdown(self) -> None:
        for name, plugin in self.plugins.items():
            try:
                plugin.shutdown()
                logger.info("关闭插件: %s", name)
            except Exception as e:
                logger.warning("关闭插件 %s 失败: %s", name, e)
