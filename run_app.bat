@echo off
cd /d "%~dp0"
echo 启动 Inbound Recorder 应用...
echo 请在浏览器中访问: http://localhost:8080
echo 按 Ctrl+C 可停止应用
echo.
dist\single_app.exe
pause