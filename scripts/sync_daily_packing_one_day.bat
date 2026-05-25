@echo off
REM 用法: sync_daily_packing_one_day.bat 2026-05-19 [calendar|business|seventeen]
cd /d "%~dp0.."
if "%~1"=="" (
  echo 用法: %~nx0 YYYY-MM-DD [stats_window]
  exit /b 2
)
set WIN=%~2
if "%WIN%"=="" set WIN=calendar
python sync_daily_packing_operlog.py "%~1" -w %WIN%
exit /b %ERRORLEVEL%
