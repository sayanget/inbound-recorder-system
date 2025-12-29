@echo off
chcp 65001 >nul
echo ========================================
echo    邮件配置向导
echo ========================================
echo.
echo 此向导将帮助您配置邮箱信息
echo.

python setup_email_config.py

if errorlevel 1 (
    echo.
    echo 配置过程出错！
    pause
)
