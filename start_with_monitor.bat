@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Inbound Recorder Monitor

if not exist "app_monitor.py" (
    echo [ERROR] app_monitor.py not found. Current dir:
    cd
    echo.
    pause
    exit /b 1
)

echo ========================================
echo   Inbound Recorder - HA Monitor
echo ========================================
echo.
echo Default ports: monitor 8081, app 8080, license 8088 ^(LICENSE_ENFORCE=1 时监控自动拉起许可服务^)
echo Override: MONITOR_PORT / PORT / APP_PORT / LICENSE_BIND_PORT
echo On Windows Hyper-V/WSL, 8057-8156 are often reserved — use e.g. MONITOR_PORT=18081 PORT=8780
echo.

REM Neon sync watch: set NEON_SYNC_WITH_MONITOR=0 to skip
if /I not "%NEON_SYNC_WITH_MONITOR%"=="0" (
    if exist "%~dp0run_watch_neon_sync.bat" (
        if exist "%~dp0neon_watch_check.ps1" (
            powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0neon_watch_check.ps1" >nul 2>&1
            if errorlevel 1 (
                echo [Neon] Starting watch_sqlite_sync_neon listener...
                start "NeonSync-Watch" "%~dp0run_watch_neon_sync.bat"
            ) else (
                echo [Neon] Listener already running, skip.
            )
        ) else (
            echo [Neon] neon_watch_check.ps1 missing, skip Neon auto-sync block.
        )
    ) else (
        echo [Neon] run_watch_neon_sync.bat not found, skip.
    )
    echo.
)

:LOOP
echo [%DATE% %TIME%] Starting app_monitor.py...
echo ----------------------------------------

set "PYTHON_CMD=python"
python --version >nul 2>&1
if errorlevel 1 (
    if exist ".venv\Scripts\python.exe" (
        echo [WARN] System python not found, using .venv
        set "PYTHON_CMD=.venv\Scripts\python.exe"
    ) else (
        echo [ERROR] No python.exe and no .venv\Scripts\python.exe
        echo Install Python or create venv, then retry.
        echo.
        pause
        exit /b 1
    )
)

echo [ENV] Python: !PYTHON_CMD!
"!PYTHON_CMD!" app_monitor.py
set MON_EXIT=!ERRORLEVEL!

echo.
echo [%DATE% %TIME%] app_monitor.py exited, code: !MON_EXIT!
echo Restarting in 5 seconds...
echo.

echo [%DATE% %TIME%] exit !MON_EXIT! >> monitor_crash.log

timeout /t 5 > nul
goto LOOP
