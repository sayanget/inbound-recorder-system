@echo off
chcp 65001 > nul
setlocal

REM Package the standalone folder (with portable Python) into a zip for distribution.
REM Recipient can extract and run build.bat without installing anything.

cd /d "%~dp0"

if not exist "%~dp0portable\python.exe" (
    echo [!] portable\python.exe not found
    echo     Run init_portable.bat first to create the portable Python env
    pause
    exit /b 1
)

echo =========================================================
echo  Packing portable distribution zip ...
echo =========================================================
echo.

REM Hand off to PowerShell for reliable cross-encoding file handling.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack_distribution.ps1"
set RC=%errorlevel%
echo.
pause
exit /b %RC%
