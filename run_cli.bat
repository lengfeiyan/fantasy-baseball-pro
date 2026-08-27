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
title Fantasy Baseball Pro - CLI

:menu
cls
echo ============================================
echo   Fantasy Baseball Pro 命令行菜单
echo ============================================
echo.
echo  [数据准备]
echo    1. 网络获取预测数据（FantasyPros，推荐首次使用）
echo    2. 生成排名 - VORP
echo    3. 生成排名 - SGP
echo    4. 准备 ADP 数据（12 小时缓存）
echo    5. 蛇形选秀模拟
echo    6. 蒙特卡洛可用性模拟
echo    7. Sleeper 挖掘（被低估球员）
echo.
echo  [阵容与 FA]
echo    8. 查看当前阵容
echo    9. 验证阵容（最近一次模拟日志）
echo   10. 更新 FA 池（内置示例）
echo   11. 生成 FA 推荐
echo   12. 更新伤病数据
echo.
echo  [其他]
echo   13. 查询球员真实数据（MLB + Statcast）
echo   14. 启动图形界面
echo    0. 退出
echo.
set "choice="
set /p choice=请选择操作: 

if "%choice%"=="1" goto fetch
if "%choice%"=="2" goto rank_vorp
if "%choice%"=="3" goto rank_sgp
if "%choice%"=="4" goto adp
if "%choice%"=="5" goto draft
if "%choice%"=="6" goto simulate
if "%choice%"=="7" goto sleeper
if "%choice%"=="8" goto roster
if "%choice%"=="9" goto validate
if "%choice%"=="10" goto fa_update
if "%choice%"=="11" goto fa_recommend
if "%choice%"=="12" goto injury
if "%choice%"=="13" goto mlb
if "%choice%"=="14" goto gui
if "%choice%"=="0" exit /b 0
goto menu

:fetch
"%PY%" -m fantasy_baseball fetch-projections
goto after

:rank_vorp
"%PY%" -m fantasy_baseball rank --method vorp
goto after

:rank_sgp
"%PY%" -m fantasy_baseball rank --method sgp
goto after

:adp
"%PY%" -m fantasy_baseball adp
goto after

:draft
set "pick="
set "strategy="
set "method="
set /p pick=选秀顺位（回车默认 5）:
if "%pick%"=="" set pick=5
set /p strategy=策略 balanced/conservative/aggressive（回车默认 balanced）:
if "%strategy%"=="" set strategy=balanced
set /p method=评分 vorp/sgp（回车默认 vorp）:
if "%method%"=="" set method=vorp
"%PY%" -m fantasy_baseball draft --pick %pick% --strategy %strategy% --method %method%
goto after

:simulate
set "pick="
set "thresh="
set "method="
set /p pick=你的顺位（回车默认 5）:
if "%pick%"=="" set pick=5
set /p thresh=最小可用率 0-1（回车默认 0.25）:
if "%thresh%"=="" set thresh=0.25
set /p method=评分 vorp/sgp（回车默认 vorp）:
if "%method%"=="" set method=vorp
"%PY%" -m fantasy_baseball simulate --user-pick %pick% --min-availability %thresh% --method %method%
goto after

:sleeper
set "minadp="
set "maxadp="
set /p minadp=最小 ADP（回车默认 80）:
if "%minadp%"=="" set minadp=80
set /p maxadp=最大 ADP（回车默认 300）:
if "%maxadp%"=="" set maxadp=300
"%PY%" -m fantasy_baseball sleeper --min-adp %minadp% --max-adp %maxadp%
goto after

:roster
"%PY%" -m fantasy_baseball roster show
goto after

:validate
"%PY%" -m fantasy_baseball validate draft_log_pick5_balanced.csv --analyze
goto after

:fa_update
"%PY%" -m fantasy_baseball fa update-fa
goto after

:fa_recommend
set "pos="
set "risk="
set "method="
set /p pos=位置筛选 All/C/1B/OF/SP...（回车默认 All）:
if "%pos%"=="" set pos=All
set /p risk=风险偏好 balanced/conservative/aggressive（回车默认 balanced）:
if "%risk%"=="" set risk=balanced
set /p method=评分 vorp/sgp（回车默认 vorp）:
if "%method%"=="" set method=vorp
"%PY%" -m fantasy_baseball fa recommend --position %pos% --risk %risk% --method %method%
goto after

:injury
"%PY%" -m fantasy_baseball fa update-injury
goto after

:mlb
set "player="
set /p player=球员姓名（如 Aaron Judge 或 Shohei Ohtani）:
if "%player%"=="" (
    echo [提示] 未输入姓名，返回菜单
    goto after
)
"%PY%" -m fantasy_baseball mlb "%player%" --statcast
goto after

:gui
start "" "%~dp0run_gui.bat"
goto after

:after
echo.
echo ============================================
pause
goto menu
