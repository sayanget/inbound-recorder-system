@echo off
chcp 65001 >nul
echo ========================================
echo    每日邮件报告服务启动程序
echo ========================================
echo.
echo 正在启动每日邮件报告服务...
echo.
echo 提示：
echo - 程序将在后台持续运行
echo - 每天会在配置的时间自动发送邮件
echo - 按 Ctrl+C 可以停止程序
echo.
echo ========================================
echo.

python daily_email_report.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo 错误：程序运行失败！
    echo.
    echo 可能的原因：
    echo 1. Python未安装或未添加到PATH
    echo 2. 缺少必要的依赖包
    echo 3. 配置文件有误
    echo.
    echo 请检查以上问题后重试
    echo ========================================
    pause
) else (
    echo.
    echo ========================================
    echo 程序已正常退出
    echo ========================================
    pause
)
