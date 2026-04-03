@echo off
REM SQLite -^> Neon：可选主库 production、测试库 sandbox，或两者依次全面同步。
REM 连接串写在 neon_sync.env（勿提交仓库）：
REM   DATABASE_URL_PRODUCTION=postgresql://...
REM   DATABASE_URL_SANDBOX=postgresql://...
REM 复制整段 URI 即可（不要带 psql 前缀）；含 &channel_binding=require 时保留或让脚本自动处理。
chcp 65001 >nul
title SQLite -^> Neon（多目标）
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "PREFIX_PY=%~dp0scripts\print_stdlib_prefix.py"
set "PYTHONHOME="
set "PYTHONEXECUTABLE="
if exist "%PY%" if exist "%PREFIX_PY%" for /f "delims=" %%i in ('""%PY%" "%PREFIX_PY%"" 2^>nul') do set "PYTHONHOME=%%i"
if defined PYTHONHOME if not exist "%PYTHONHOME%\Lib\os.py" set "PYTHONHOME="

if not exist "%PY%" (
  echo ERROR: 未找到 .venv\Scripts\python.exe
  echo 请在项目根目录执行: py -3 -m venv .venv
  pause
  exit /b 1
)

echo.
echo   1^) 主库 production   ^(DATABASE_URL_PRODUCTION^)
echo   2^) 测试库 sandbox    ^(DATABASE_URL_SANDBOX^)
echo   3^) 全面同步          ^(先 production，再 sandbox^)
echo   4^) 退出
echo.
set /p SYNC_PICK=请选择 [1-4]: 

if "%SYNC_PICK%"=="1" (
  "%PY%" scripts\sync_sqlite_neon_targets.py --production
  goto :end
)
if "%SYNC_PICK%"=="2" (
  "%PY%" scripts\sync_sqlite_neon_targets.py --sandbox
  goto :end
)
if "%SYNC_PICK%"=="3" (
  "%PY%" scripts\sync_sqlite_neon_targets.py --all
  goto :end
)
if "%SYNC_PICK%"=="4" (
  exit /b 0
)
echo 无效输入。
pause
exit /b 2

:end
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE% equ 0 (
  echo 完成，退出码 %EXITCODE%
) else (
  echo 失败，退出码 %EXITCODE%
)
pause
exit /b %EXITCODE%
