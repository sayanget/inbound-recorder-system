@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:main_menu
cls
echo ========================================
echo   Antigravity 迁移工具
echo ========================================
echo.
echo 请选择操作:
echo.
echo [备份选项]
echo 1. 快速备份 (仅 skills 和配置，不含历史) - 推荐
echo 2. 完整备份 (包含所有对话历史)
echo 3. 自定义备份路径
echo.
echo [恢复选项]
echo 4. 自动恢复 (查找最新备份文件)
echo 5. 手动恢复 (指定备份文件路径)
echo.
echo [其他]
echo 6. 查看现有备份文件
echo 7. 退出
echo.

set /p choice="请输入选项 (1-7): "

if "%choice%"=="1" goto quick_backup
if "%choice%"=="2" goto full_backup
if "%choice%"=="3" goto custom_backup
if "%choice%"=="4" goto auto_restore
if "%choice%"=="5" goto manual_restore
if "%choice%"=="6" goto list_backups
if "%choice%"=="7" goto exit_program

echo.
echo [错误] 无效选项
timeout /t 2 >nul
goto main_menu

:quick_backup
cls
echo ========================================
echo   快速备份模式
echo ========================================
echo.
echo [说明] 仅备份 skills 和配置，跳过历史记录
echo [优点] 文件小 (~265 MB)，传输快
echo.
set /p confirm="确认开始备份? (Y/N): "
if /i not "!confirm!"=="Y" goto main_menu

echo.
powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -SkipHistory
echo.
pause
goto main_menu

:full_backup
cls
echo ========================================
echo   完整备份模式
echo ========================================
echo.
echo [说明] 备份所有内容，包含对话历史
echo [警告] 文件可能很大 (8+ GB)
echo.
set /p confirm="确认开始备份? (Y/N): "
if /i not "!confirm!"=="Y" goto main_menu

echo.
powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1"
echo.
pause
goto main_menu

:custom_backup
cls
echo ========================================
echo   自定义备份
echo ========================================
echo.
set /p customPath="请输入备份路径 (例: E:\my_backup): "
if "!customPath!"=="" (
    echo [错误] 路径不能为空
    timeout /t 2 >nul
    goto main_menu
)

set /p skipHistory="是否跳过历史记录? (Y/N): "
echo.

if /i "!skipHistory!"=="Y" (
    powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -BackupPath "!customPath!" -SkipHistory
) else (
    powershell -ExecutionPolicy Bypass -File "%~dp0backup_antigravity.ps1" -BackupPath "!customPath!"
)
echo.
pause
goto main_menu

:auto_restore
cls
echo ========================================
echo   自动恢复模式
echo ========================================
echo.
echo 正在查找最新备份文件...
echo.

:: 查找最新的备份文件
set "latestBackup="
for /f "delims=" %%i in ('dir /b /o-d "D:\antigravity_backup_*.zip" 2^>nul') do (
    set "latestBackup=D:\%%i"
    goto found_backup
)

echo [错误] 未找到备份文件
echo.
echo 提示: 请确保备份文件位于 D:\ 目录
echo       文件名格式: antigravity_backup_YYYYMMDD_HHMMSS.zip
echo.
pause
goto main_menu

:found_backup
echo 找到备份文件:
echo !latestBackup!
echo.

:: 显示文件信息
for %%A in ("!latestBackup!") do (
    set "fileSize=%%~zA"
    set "fileDate=%%~tA"
)
set /a fileSizeMB=!fileSize! / 1048576
echo 文件大小: !fileSizeMB! MB
echo 修改时间: !fileDate!
echo.

set /p confirm="使用此文件恢复? (Y/N): "
if /i not "!confirm!"=="Y" goto main_menu

set /p skipHistory="是否跳过历史记录恢复? (Y/N): "
echo.

if /i "!skipHistory!"=="Y" (
    powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!latestBackup!" -SkipHistory
) else (
    powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!latestBackup!"
)
echo.
pause
goto main_menu

:manual_restore
cls
echo ========================================
echo   手动恢复模式
echo ========================================
echo.
set /p backupPath="请输入备份文件完整路径: "

if "!backupPath!"=="" (
    echo [错误] 路径不能为空
    timeout /t 2 >nul
    goto main_menu
)

if not exist "!backupPath!" (
    echo [错误] 文件不存在: !backupPath!
    echo.
    pause
    goto main_menu
)

echo.
echo 文件: !backupPath!
for %%A in ("!backupPath!") do (
    set "fileSize=%%~zA"
    set /a fileSizeMB=!fileSize! / 1048576
    echo 大小: !fileSizeMB! MB
)
echo.

set /p confirm="确认恢复? (Y/N): "
if /i not "!confirm!"=="Y" goto main_menu

set /p skipHistory="是否跳过历史记录恢复? (Y/N): "
echo.

if /i "!skipHistory!"=="Y" (
    powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!backupPath!" -SkipHistory
) else (
    powershell -ExecutionPolicy Bypass -File "%~dp0restore_antigravity.ps1" -BackupZipPath "!backupPath!"
)
echo.
pause
goto main_menu

:list_backups
cls
echo ========================================
echo   现有备份文件
echo ========================================
echo.
echo 在 D:\ 目录下的备份文件:
echo.

set "foundFiles=0"
for /f "delims=" %%i in ('dir /b /o-d "D:\antigravity_backup_*.zip" 2^>nul') do (
    set /a foundFiles+=1
    for %%A in ("D:\%%i") do (
        set "fileSize=%%~zA"
        set /a fileSizeMB=!fileSize! / 1048576
        echo [!foundFiles!] %%i
        echo     大小: !fileSizeMB! MB
        echo     时间: %%~tA
        echo.
    )
)

if !foundFiles!==0 (
    echo 未找到备份文件
)

echo.
pause
goto main_menu

:exit_program
cls
echo.
echo 感谢使用 Antigravity 迁移工具！
echo.
timeout /t 1 >nul
exit /b 0
