@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================================
echo               Project Backup Tool (Inbound System)
echo ========================================================
echo.

REM 1. Get timestamp (YYYYMMDD_HHMMSS) using PowerShell
REM This is robust and works on all modern Windows versions
for /f "delims=" %%I in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set timestamp=%%I

if "%timestamp%"=="" (
    echo [ERROR] Failed to get timestamp. Backup aborted.
    pause
    exit /b
)

set "BACKUP_ROOT_DIR=Backups"
set "BACKUP_DIR=%BACKUP_ROOT_DIR%\backup_%timestamp%"

REM 2. Create backup directories
if not exist "%BACKUP_ROOT_DIR%" mkdir "%BACKUP_ROOT_DIR%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [INFO] Creating backup directory: %BACKUP_DIR%
echo.

REM 3. Copy Python source files (.py)
echo [1/5] Copying Python source code...
xcopy "*.py" "%BACKUP_DIR%\" /Y /Q >nul
if %ERRORLEVEL% EQU 0 ( echo     - Success ) else ( echo     ! Failed or no files )

REM 4. Copy Database (.db)
echo [2/5] Copying database file...
if exist "inbound.db" (
    xcopy "inbound.db" "%BACKUP_DIR%\" /Y /Q /C >nul
    echo     - Success (inbound.db)
) else (
    echo     ! Database file not found (inbound.db)
)

REM 5. Copy Static Resources (static folder)
echo [3/5] Copying static resources...
if exist "static" (
    xcopy "static" "%BACKUP_DIR%\static\" /E /I /Y /Q >nul
    echo     - Success
) else (
    echo     ! static folder not found
)

REM 6. Copy Config and Scripts (.bat, .md, .txt)
echo [4/5] Copying docs and scripts...
xcopy "*.bat" "%BACKUP_DIR%\" /Y /Q >nul
xcopy "*.md" "%BACKUP_DIR%\" /Y /Q >nul
if exist "requirements.txt" xcopy "requirements.txt" "%BACKUP_DIR%\" /Y /Q >nul

echo.
echo ========================================================
echo [OK] Backup Completed Successfully!
echo.
echo Backup Path: %CD%\%BACKUP_DIR%
echo ========================================================
echo.
pause
