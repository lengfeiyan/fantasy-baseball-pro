# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Fantasy Baseball Pro.

打包命令：pyinstaller fbtool.spec --clean --noconfirm
输出在 dist/FantasyBaseballPro/
"""

import os

block_cipher = None

# 入口脚本：无参数时启动 GUI
a = Analysis(
    ["src/fantasy_baseball/entry.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # 运行时文件打包到 exe 旁边（用户可编辑）
        ("config.yaml", "."),
        ("data", "data"),
        # 修复 L6：帮助文档随 exe 一起分发
        ("USER_GUIDE.md", "."),
    ],
    hiddenimports=[
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "sqlite3",
        "yaml",
        "urllib.request",
        "html.parser",
        "json",
        "csv",
        "importlib.util",
        "fantasy_baseball",
        "fantasy_baseball.cli",
        "fantasy_baseball.gui.app",
        "fantasy_baseball.core.sgp",
        "fantasy_baseball.data_fetch.mlb_api",
        "fantasy_baseball.data_fetch.projections",
        "fantasy_baseball.data_fetch.statcast",
        "fantasy_baseball.fa.analyzer",
        "fantasy_baseball.fa.real_time",
        "fantasy_baseball.fa.recommendation",
        "fantasy_baseball.gui.tabs.analysis",
        "fantasy_baseball.gui.tabs.config_tab",
        "fantasy_baseball.gui.tabs.data",
        "fantasy_baseball.gui.tabs.draft_center",
        "fantasy_baseball.gui.tabs.explore",
        "fantasy_baseball.gui.tabs.fa_tab",
        "fantasy_baseball.gui.tabs.home",
        "fantasy_baseball.gui.tabs.plugins_tab",
        "fantasy_baseball.gui.tabs.roster",
        "fantasy_baseball.gui.tabs.sleeper",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numba",
        "llvmlite",
        "pytest",
        "IPython",
        "matplotlib",
        "PIL",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FantasyBaseballPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 模式，无控制台窗口
    disable_windowed_traceback=False,
    icon=None,  # 如有 icon.ico 可改为 icon="icon.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FantasyBaseballPro",
)
