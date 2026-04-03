@echo off
chcp 65001 > nul
title 自动配置计划任务 - Inbound Watchdog
cd /d "%~dp0"

echo ========================================
echo       自动配置 Windows 计划任务
echo ========================================
echo.
echo 任务名称: InboundWatchdog
echo 脚本路径: %CD%\service_watchdog.ps1
echo 执行频率: 每 5 分钟
echo.

:: 检查是否以管理员身份运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 请右键以“管理员身份”运行此脚本！
    echo.
    pause
    exit /b
)

:: 构建命令
set TASK_NAME=InboundWatchdog
set PS_PATH=%CD%\service_watchdog.ps1
set ACTION="powershell.exe -ExecutionPolicy Bypass -File \"%PS_PATH%\""

:: 尝试创建计划任务
:: /sc minute /mo 5 = 每5分钟运行一次
:: /f = 如果存在则强制覆盖
schtasks /create /tn "%TASK_NAME%" /tr %ACTION% /sc minute /mo 5 /f /rl HIGHEST

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo [成功] 计划任务已成功创建！
    echo ----------------------------------------
    echo 1. 该任务将每 5 分钟自动运行一次 service_watchdog.ps1
    echo 2. 您可以在“任务计划程序”中找到并管理它
    echo 3. 您也可以手动运行：schtasks /run /tn "%TASK_NAME%"
    echo ========================================
) else (
    echo.
    echo [失败] 无法创建计划任务，请检查权限。
)

echo.
pause
