@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================================
echo               项目自动备份工具 (Inbound System)
echo ========================================================
echo.

REM 1. 获取标准化时间戳 (YYYYMMDD_HHMMSS) 使用 PowerShell
for /f "delims=" %%I in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set timestamp=%%I

if "%timestamp%"=="" (
    echo [ERROR] 无法获取时间戳，备份失败。
    pause
    exit /b
)

set "BACKUP_ROOT_DIR=Backups"
set "BACKUP_DIR=%BACKUP_ROOT_DIR%\backup_%timestamp%"

REM 2. 创建备份目录
if not exist "%BACKUP_ROOT_DIR%" mkdir "%BACKUP_ROOT_DIR%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [INFO] 正在创建备份目录: %BACKUP_DIR%
echo.

REM 3. 复制核心代码文件 (.py)
echo [1/5] 正在复制 Python 源代码...
xcopy "*.py" "%BACKUP_DIR%\" /Y /Q >nul
if %ERRORLEVEL% EQU 0 ( echo     - 成功 ) else ( echo     ! 失败或无文件 )

REM 4. 复制数据库文件 (.db)
echo [2/5] 正在复制数据库文件...
if exist "inbound.db" (
    xcopy "inbound.db" "%BACKUP_DIR%\" /Y /Q /C >nul
    echo     - 成功 (inbound.db)
) else (
    echo     ! 未找到数据库文件 (inbound.db)
)

REM 5. 复制静态资源 (static 文件夹)
echo [3/5] 正在复制静态资源 (static)...
if exist "static" (
    xcopy "static" "%BACKUP_DIR%\static\" /E /I /Y /Q >nul
    echo     - 成功
) else (
    echo     ! 未找到 static 文件夹
)

REM 6. 复制配置文件和脚本 (.bat, .md, .txt)
echo [4/5] 正在复制文档和脚本...
xcopy "*.bat" "%BACKUP_DIR%\" /Y /Q >nul
xcopy "*.md" "%BACKUP_DIR%\" /Y /Q >nul
if exist "requirements.txt" xcopy "requirements.txt" "%BACKUP_DIR%\" /Y /Q >nul

REM 7. 忽略无关文件 (__pycache__, git, etc)
REM (xcopy 默认不复制隐藏文件夹，且上述显式指定了文件类型，所以比较安全)

echo.
echo ========================================================
echo [OK] 备份已完成！
echo.
echo 备份路径: %CD%\%BACKUP_DIR%
echo ========================================================
echo.
pause
