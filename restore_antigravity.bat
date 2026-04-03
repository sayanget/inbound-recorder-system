@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Antigravity 恢复工具
echo ========================================
echo.

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 建议以管理员权限运行此脚本
    echo.
    pause
)

echo 请选择恢复模式:
echo.
echo 1. 自动选择备份文件 (从 D:\ 查找最新备份)
echo 2. 手动指定备份文件路径
echo 3. 退出
echo.

set /p choice="请输入选项 (1-3): "

if "%choice%"=="1" (
    echo.
    echo 正在查找最新备份文件...
    
    :: 查找最新的备份文件
    for /f "delims=" %%i in ('dir /b /o-d "D:\antigravity_backup_*.zip" 2^>nul') do (
        set "latestBackup=D:\%%i"
        goto found
    )
    
    echo [错误] 未找到备份文件
    echo 请确保备份文件位于 D:\ 目录
    goto end
    
    :found
    echo 找到备份文件: !latestBackup!
    echo.
    set /p confirm="使用此文件恢复? (Y/N): "
    if /i "!confirm!"=="Y" (
        set /p skipHistory="是否跳过历史记录恢复? (Y/N): "
        echo.
        if /i "!skipHistory!"=="Y" (
            powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!latestBackup!" -SkipHistory
        ) else (
            powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!latestBackup!"
        )
    ) else (
        echo 已取消恢复
    )
    goto end
)

if "%choice%"=="2" (
    echo.
    set /p backupPath="请输入备份文件完整路径: "
    
    if not exist "!backupPath!" (
        echo [错误] 文件不存在: !backupPath!
        goto end
    )
    
    set /p skipHistory="是否跳过历史记录恢复? (Y/N): "
    echo.
    if /i "!skipHistory!"=="Y" (
        powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!backupPath!" -SkipHistory
    ) else (
        powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!backupPath!"
    )
    goto end
)

if "%choice%"=="3" (
    echo 已退出
    goto end
)

echo 无效选项，请重新运行脚本
pause

:end
echo.
echo 按任意键退出...
pause >nul
