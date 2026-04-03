@echo off
chcp 65001 >nul
echo ========================================
echo   Inbound Recorder 启动脚本
echo ========================================

REM 检查Python是否已安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.7或更高版本
    pause
    exit /b 1
)

REM 检查pip是否已安装
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到pip，请确保Python安装时包含了pip
    pause
    exit /b 1
)

REM 安装依赖
echo 正在安装依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)

REM 启动应用
echo.
echo 启动 Inbound Recorder 应用...
echo.
echo 请在浏览器中访问以下地址:
echo http://localhost:8080
echo.
echo 按 Ctrl+C 可停止应用
echo.

set FLASK_ENV=production
python single_app.py

pause