@echo off
REM Manual one-shot sync: SQLite -> Neon (staging, verify, swap).
chcp 65001 >nul
title SQLite to Neon Sync
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PREFIX_PY=%~dp0scripts\print_stdlib_prefix.py"
set "PYTHONHOME="
set "PYTHONEXECUTABLE="
if exist "%PY%" if exist "%PREFIX_PY%" for /f "delims=" %%i in ('""%PY%" "%PREFIX_PY%"" 2^>nul') do set "PYTHONHOME=%%i"
if defined PYTHONHOME if not exist "%PYTHONHOME%\Lib\os.py" set "PYTHONHOME="

if not exist "%PY%" (
  echo [ERROR] Missing .venv\Scripts\python.exe
  echo Run: py -3 -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements-neon-sync.txt
  pause
  exit /b 1
)

echo ========================================
echo   SQLite -> Neon Sync
echo ========================================
echo Project: %CD%
echo.
echo [%date% %time%] Start...
echo.

"%PY%" scripts\sqlite_to_postgres.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% equ 0 (
  echo [%date% %time%] Done. Exit code %EXITCODE%
) else (
  echo [%date% %time%] Failed. Exit code %EXITCODE%
)
echo.
pause
exit /b %EXITCODE%
