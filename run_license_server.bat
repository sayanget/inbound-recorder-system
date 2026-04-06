@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动许可证服务（默认 http://127.0.0.1:8088/admin ）
echo 需在 .env 中配置 LICENSE_ADMIN_KEY；主业务 single_app 仍用 8080 时请另开窗口运行。
echo.
python -m license_server.app
if errorlevel 1 pause
