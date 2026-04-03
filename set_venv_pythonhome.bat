@echo off
REM Same PYTHONHOME probe as run_neon_nightly_sync.bat (for manual use).
set "PY=%~dp0.venv\Scripts\python.exe"
set "PREFIX_PY=%~dp0scripts\print_stdlib_prefix.py"
set "PYTHONHOME="
set "PYTHONEXECUTABLE="
if exist "%PY%" if exist "%PREFIX_PY%" for /f "delims=" %%i in ('""%PY%" "%PREFIX_PY%"" 2^>nul') do set "PYTHONHOME=%%i"
if defined PYTHONHOME if not exist "%PYTHONHOME%\Lib\os.py" set "PYTHONHOME="
goto :eof
