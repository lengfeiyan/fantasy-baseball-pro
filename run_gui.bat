@echo off
cd /d "%~dp0"
title Fantasy Baseball Pro - GUI
set PYTHONPATH=src

echo ============================================
echo   Fantasy Baseball Pro 图形界面
echo ============================================
echo.

python -m fantasy_baseball gui

if errorlevel 1 (
    echo.
    echo [错误] GUI 启动失败，请检查：
    echo   1. Python 是否在 PATH 中（命令行输入 python --version 验证）
    echo   2. 依赖是否安装（pip install -r requirements.txt）
    echo.
    pause
)
