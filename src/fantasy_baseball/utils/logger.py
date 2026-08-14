"""统一日志配置。

提供 ``get_logger(name)``，输出同时写入 ``logs/YYYY-MM-DD.log``（轮转）与控制台。
日志目录基于项目根（``config.yaml`` 所在目录），不再依赖调用方的工作目录。
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict

# 项目根：打包后用 exe 所在目录；开发环境用 __file__ 反推（向上回溯 4 层）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # PyInstaller 打包后：用 exe 所在目录（exe 旁边放 config.yaml/data/ 等运行时文件）
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 缓存已配置的 logger，避免重复添加 handler
_configured: Dict[str, logging.Logger] = {}


def get_logger(name: str = "fantasy_baseball") -> logging.Logger:
    """获取配置好的 logger。

    首次调用时创建文件 + 控制台 handler；同名 logger 后续调用直接复用，
    不会重复添加 handler（修复旧版在多次 import 时叠加 handler 的问题）。
    """
    if name in _configured:
        return _configured[name]

    # 确保日志目录存在（延迟创建，避免在 import 阶段触发 IO）
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        # 日志目录不可用时退化为仅控制台输出
        pass

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # 避免向 root logger 冒泡造成重复输出

    if not logger.handlers:
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

        # 控制台 handler 始终添加
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        logger.addHandler(console)

        # 文件 handler 仅在目录可用时添加
        try:
            log_file = os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d}.log")
            file_handler = RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass

    _configured[name] = logger
    return logger
