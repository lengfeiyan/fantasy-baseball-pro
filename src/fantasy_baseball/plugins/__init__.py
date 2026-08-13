"""插件系统。

迁移自旧版 ``plugins/``。插件目录基于项目根解析，不再依赖 CWD。
"""

from .base_plugin import BasePlugin
from .plugin_manager import PluginManager

__all__ = ["BasePlugin", "PluginManager"]
