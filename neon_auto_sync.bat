@echo off
REM Unified entry for SQLite -> Neon auto sync.
REM Target URL priority: DATABASE_URL, then DATABASE_URL_PRODUCTION.
chcp 65001 >nul
title Inbound Neon Auto Sync
cd /d "%~dp0"

:menu
echo.
echo ========================================
echo   Neon Auto Sync (SQLite -^> current target URL)
echo ========================================
echo   Configure neon_sync.env first.
echo   Recommended: DATABASE_URL=postgresql://... (or only DATABASE_URL_PRODUCTION=...)
echo.
echo   [1] Start file watcher sync (keep window open)
echo   [2] Install startup watcher (runs after login)
echo   [3] Install nightly sync at 00:00 (requires admin)
echo   [4] First-time setup (deps + neon_sync.env template)
echo   [5] Exit
echo ========================================
set /p PICK=Select [1-5]: 

if "%PICK%"=="1" call :run_watch
if "%PICK%"=="2" call :install_startup
if "%PICK%"=="3" call :install_nightly
if "%PICK%"=="4" call :first_setup
if "%PICK%"=="5" exit /b 0
if not "%PICK%"=="1" if not "%PICK%"=="2" if not "%PICK%"=="3" if not "%PICK%"=="4" if not "%PICK%"=="5" echo Invalid selection.
goto :menu

:run_watch
echo.
start "NeonSync-Watch" "%~dp0run_watch_neon_sync.bat"
echo Watcher started in a new window. Close it to stop auto sync.
pause
goto :menu

:install_startup
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_neon_watch_startup.ps1"
pause
goto :menu

:install_nightly
echo.
call "%~dp0install_neon_nightly_sync.bat"
goto :menu

:first_setup
echo.
call "%~dp0setup_neon_auto_sync.bat"
goto :menu
