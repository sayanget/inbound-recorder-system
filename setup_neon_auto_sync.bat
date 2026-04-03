@echo off
REM One-click setup: deps + neon_sync.env template + logs directory.
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Inbound: Neon Auto Sync Setup
echo ========================================
echo Project dir: %CD%
echo.

if not exist "logs" mkdir logs

if not exist "neon_sync.env" (
  if exist "neon_sync.env.example" (
    copy /Y "neon_sync.env.example" "neon_sync.env" >nul
    echo [OK] Created neon_sync.env from neon_sync.env.example
    echo [IMPORTANT] Edit neon_sync.env and set DATABASE_URL (or DATABASE_URL_PRODUCTION).
    echo.
  ) else (
    echo [ERROR] Missing neon_sync.env.example
    exit /b 1
  )
) else (
  echo [INFO] neon_sync.env already exists
)

echo [pip] Installing requirements-neon-sync.txt ...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip install -r requirements-neon-sync.txt
) else (
  python -m pip install -r requirements-neon-sync.txt
)
if errorlevel 1 (
  echo [FAIL] pip install failed. Check Python and network.
  exit /b 1
)

echo.
echo ========================================
echo   Setup complete (verify target URL)
echo ========================================
echo 1. Open %CD%\neon_sync.env
echo 2. Set DATABASE_URL=postgresql://...   (or DATABASE_URL_PRODUCTION=...)
echo 3. Start watcher sync: run_watch_neon_sync.bat
echo 4. Optional startup watcher: run install_neon_watch_startup.ps1
echo.
echo Log file: %CD%\logs\neon_sync.log
echo ========================================
pause
exit /b 0
