"""PyInstaller 打包专用入口脚本。

不使用相对导入（避免 __main__ 被当成顶层脚本时包内导入失败）。
PyInstaller spec 指向此文件作为入口。
"""

import sys
import os

# 确保包可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fantasy_baseball.cli import main

if __name__ == "__main__":
    sys.exit(main())
