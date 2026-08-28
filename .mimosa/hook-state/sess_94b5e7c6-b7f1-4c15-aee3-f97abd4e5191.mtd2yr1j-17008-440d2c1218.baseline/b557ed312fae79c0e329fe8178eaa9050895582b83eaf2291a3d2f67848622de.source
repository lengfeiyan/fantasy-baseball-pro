"""插件基类：所有自定义插件必须继承。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BasePlugin(ABC):
    """插件抽象基类。"""

    VERSION = "1.0.0"
    DESCRIPTION = "No description provided"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
        self.version = getattr(self, "VERSION", "1.0.0")

    @abstractmethod
    def initialize(self) -> bool:
        """初始化插件，返回是否成功。"""

    @abstractmethod
    def shutdown(self) -> bool:
        """关闭插件，返回是否成功。"""

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": getattr(self, "DESCRIPTION", "No description provided"),
        }

    def configure(self, config: Dict[str, Any]) -> bool:
        try:
            self.config.update(config)
            return True
        except Exception:
            return False
