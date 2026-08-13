"""模块入口：``python -m fantasy_baseball``。

无参数时启动 GUI；带子命令时执行对应命令行操作。
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
