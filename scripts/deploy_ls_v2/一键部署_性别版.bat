@echo off
chcp 65001 >nul
setlocal
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 python，请先安装 Python 3.10+ 并勾选 Add to PATH。
    pause
    exit /b 1
)
python "%~dp0pc_deploy_gender.py" %*
if errorlevel 1 (
    echo.
    echo [异常退出] 请检查上方报错信息。
    pause
)
