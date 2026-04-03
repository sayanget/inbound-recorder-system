@echo off
REM Watch local SQLite changes and sync to Neon.
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PREFIX_PY=%~dp0scripts\print_stdlib_prefix.py"
set "PYTHONHOME="
set "PYTHONEXECUTABLE="
if exist "%PY%" if exist "%PREFIX_PY%" for /f "delims=" %%i in ('""%PY%" "%PREFIX_PY%"" 2^>nul') do set "PYTHONHOME=%%i"
if defined PYTHONHOME if not exist "%PYTHONHOME%\Lib\os.py" set "PYTHONHOME="

if not exist "neon_sync.env" if not exist ".env" (
  echo [ERROR] Missing neon_sync.env and .env
  echo Run setup_neon_auto_sync.bat first.
  pause
  exit /b 1
)

if not exist "%PY%" (
  echo [ERROR] Missing .venv\Scripts\python.exe
  echo Run: py -3 -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements-neon-sync.txt
  pause
  exit /b 1
)

echo [%date% %time%] Starting watch_sqlite_sync_neon.py (Ctrl+C to stop)...
echo Log: %CD%\logs\neon_sync.log
echo.

"%PY%" scripts\watch_sqlite_sync_neon.py
set EXITCODE=%ERRORLEVEL%
exit /b %EXITCODE%
