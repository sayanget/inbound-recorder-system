@echo off
title Inbound Recorder 快速启动
cd /d "%~dp0"

echo ========================================
echo   Inbound Recorder 快速启动脚本
echo ========================================
echo.

:: 检查是否已构建EXE文件，优先使用EXE启动
if exist "dist\single_app.exe" (
    echo 发现EXE文件，正在启动...
    echo.
    echo 请在浏览器中访问: http://localhost:8080
    echo 按 Ctrl+C 可停止应用
    echo.
    echo ========================================
    dist\single_app.exe
) else (
    echo 未发现EXE文件，正在使用Python脚本启动...
    echo.
    echo 请在浏览器中访问: http://localhost:8080
    echo 按 Ctrl+C 可停止应用
    echo.
    echo ========================================
    python single_app.py
)

pause