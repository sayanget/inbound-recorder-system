@echo off
REM Core nightly runner: SQLite (inbound.db) -> Neon PostgreSQL.
chcp 65001 >nul
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
  exit /b 1
)

echo [%date% %time%] Running nightly_neon_sync.py ...
"%PY%" scripts\nightly_neon_sync.py
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% equ 0 (
  echo [%date% %time%] OK - exit code %EXITCODE%
) else (
  echo [%date% %time%] FAILED - exit code %EXITCODE%
  echo Log: %CD%\logs\neon_sync.log
)
exit /b %EXITCODE%
