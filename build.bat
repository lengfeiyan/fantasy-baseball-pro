@echo off
chcp 65001 >nul
echo ============================================
echo   Fantasy Baseball Pro 打包脚本
echo ============================================
echo.

echo [1/4] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo       未安装，正在安装...
    pip install pyinstaller
)

echo [2/4] 设置环境变量...
set PYTHONPATH=src

echo [3/4] 开始打包（可能需要几分钟）...
pyinstaller fbtool.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查上方错误信息。
    pause
    exit /b 1
)

echo [4/4] 打包完成！
echo.
echo   输出目录: dist\FantasyBaseballPro\
echo   启动程序: dist\FantasyBaseballPro\FantasyBaseballPro.exe
echo.
echo   注意: 运行时需要以下文件在 exe 旁边:
echo     - config.yaml（已自动打包）
echo     - data\ 目录（已自动打包）
echo   首次运行会自动创建 fantasy_baseball.db 和 logs\
echo.
pause
