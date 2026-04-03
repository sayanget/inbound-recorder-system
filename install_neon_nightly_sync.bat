@echo off
chcp 65001 >nul
title Install nightly Neon sync task (00:00 daily)
cd /d "%~dp0"

echo ========================================
echo   Inbound: nightly SQLite -^> Neon sync
echo ========================================
echo.
echo Task name: InboundNeonNightlySync
echo Runs at:   every day 00:00 (midnight local time)
echo Script:    %CD%\run_neon_nightly_sync.bat
echo.
echo Before running: copy neon_sync.env.example to neon_sync.env
echo and set DATABASE_URL (or set DATABASE_URL in .env).
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Run this batch as Administrator.
    pause
    exit /b 1
)

set "TASK_NAME=InboundNeonNightlySync"
set "BAT_PATH=%CD%\run_neon_nightly_sync.bat"

schtasks /create /tn "%TASK_NAME%" /tr "\"%BAT_PATH%\"" /sc DAILY /st 00:00 /f /rl HIGHEST

if %errorLevel% equ 0 (
    echo.
    echo [OK] Scheduled task created. Check Task Scheduler: %TASK_NAME%
    echo Logs: %CD%\logs\neon_sync.log
) else (
    echo [FAIL] schtasks returned error.
)
echo.
pause
