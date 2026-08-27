@echo off
cd /d "%~dp0"
rem 便携运行时优先：整个项目文件夹拷到无 Python 的电脑也能直接运行
if exist "%~dp0runtime\python.exe" (
    set "PY=%~dp0runtime\python.exe"
    set "TCL_LIBRARY=%~dp0runtime\tcl\tcl8.6"
    set "TK_LIBRARY=%~dp0runtime\tcl\tk8.6"
) else (
    set "PY=python"
    set "PYTHONPATH=src"
)
title Fantasy Baseball Pro - GUI
set PYTHONPATH=src

echo ============================================
echo   Fantasy Baseball Pro 图形界面
echo ============================================
echo.

"%PY%" -m fantasy_baseball gui

if not %errorlevel% == 0 (
    echo.
    echo [错误] GUI 启动失败，请检查：
    echo   1. Python 是否在 PATH 中（命令行输入 python --version 验证）
    echo   2. 依赖是否安装（pip install -r requirements.txt）
    echo.
    pause
)
