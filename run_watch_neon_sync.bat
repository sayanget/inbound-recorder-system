@echo off
REM Watch local SQLite changes and sync to Neon.
chcp 65001 >nul
cd /d "%~dp0"

set "EXITCODE=0"
set "PY="
set "PYTHONHOME="
set "PYTHONEXECUTABLE="

if not exist "neon_sync.env" if not exist ".env" (
  echo [ERROR] Missing neon_sync.env and .env
  echo Run setup_neon_auto_sync.bat first.
  set EXITCODE=1
  goto :END
)

REM Prefer .venv only when interpreter is healthy (stdlib + watchdog)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import encodings, watchdog" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%~dp0.venv\Scripts\python.exe"
    goto :RUN
  )
  echo [WARN] .venv\Scripts\python.exe is missing deps or broken; trying system Python...
)

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] No working Python found.
  echo Fix .venv: py -3 -m venv .venv
  echo   then: .venv\Scripts\python.exe -m pip install -r requirements-neon-sync.txt
  echo Or install globally: pip install -r requirements-neon-sync.txt
  set EXITCODE=1
  goto :END
)

set "PY=python"
python -c "import encodings, watchdog" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] watchdog not installed for system Python.
  echo Run: pip install -r requirements-neon-sync.txt
  set EXITCODE=1
  goto :END
)

:RUN
echo [%date% %time%] Starting watch_sqlite_sync_neon.py (Ctrl+C to stop)...
echo Python: %PY%
echo Log: %CD%\logs\neon_sync.log
echo.

if not exist "logs" mkdir logs

"%PY%" scripts\watch_sqlite_sync_neon.py
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% neq 0 (
  echo.
  echo [ERROR] watch_sqlite_sync_neon.py exited with code %EXITCODE%
  echo See: %CD%\logs\neon_sync.log
)

:END
if %EXITCODE% neq 0 pause
exit /b %EXITCODE%
