@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Antigravity 备份工具
echo ========================================
echo.

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 建议以管理员权限运行此脚本
    echo.
    pause
)

echo 请选择备份模式:
echo.
echo 1. 快速备份 (仅 skills 和配置，不含历史记录) - 推荐
echo 2. 完整备份 (包含所有对话历史)
echo 3. 自定义备份路径
echo 4. 退出
echo.

set /p choice="请输入选项 (1-4): "

if "%choice%"=="1" (
    echo.
    echo [模式] 快速备份 - 跳过历史记录
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -SkipHistory
    goto end
)

if "%choice%"=="2" (
    echo.
    echo [模式] 完整备份 - 包含历史记录
    echo.
    echo [警告] 此模式可能生成较大文件 (8+ GB)
    set /p confirm="确认继续? (Y/N): "
    if /i "!confirm!"=="Y" (
        powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1"
    ) else (
        echo 已取消备份
        goto end
    )
    goto end
)

if "%choice%"=="3" (
    echo.
    set /p customPath="请输入备份路径 (例: E:\my_backup): "
    set /p skipHistory="是否跳过历史记录? (Y/N): "
    echo.
    if /i "!skipHistory!"=="Y" (
        powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -BackupPath "!customPath!" -SkipHistory
    ) else (
        powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -BackupPath "!customPath!"
    )
    goto end
)

if "%choice%"=="4" (
    echo 已退出
    goto end
)

echo 无效选项，请重新运行脚本
pause

:end
echo.
echo 按任意键退出...
pause >nul
