@echo off

REM 双击运行：将本地 inbound.db 同步到 Neon PostgreSQL

REM 需先在项目根目录配置 neon_sync.env 或 .env 中的 DATABASE_URL

chcp 65001 >nul

title SQLite 同步到 Neon

cd /d "%~dp0"



echo ========================================

echo   本地 SQLite -^> Neon 同步

echo ========================================

echo 项目目录: %CD%

echo 日志文件: %CD%\logs\neon_sync.log

echo.

if not exist "%~dp0neon_sync.env" if not exist "%~dp0.env" (

  echo [提示] 未找到 neon_sync.env 或 .env

  echo 请复制 neon_sync.env.example 为 neon_sync.env，编辑并填写:

  echo   DATABASE_URL=postgresql://用户:密码@主机/库名?sslmode=require

  echo.

)

call "%~dp0run_neon_nightly_sync.bat"

set SYNC_EXIT=%ERRORLEVEL%



echo.

if %SYNC_EXIT% equ 0 (

  echo [完成] 同步成功。

) else (

  echo [失败] 退出码 %SYNC_EXIT%，请查看上方输出或日志。

)

echo.

pause

exit /b %SYNC_EXIT%


