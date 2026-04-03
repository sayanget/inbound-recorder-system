@echo off
chcp 65001 >nul
echo ========================================
echo    测试邮件发送
echo ========================================
echo.
echo 此脚本将立即发送一封测试邮件
echo 邮件内容为昨天的数据汇总
echo.
echo 收件人: sayanget@yahoo.com
echo.
set /p confirm=确认发送测试邮件吗？(Y/N): 

if /i "%confirm%"=="Y" (
    echo.
    echo 正在发送测试邮件...
    echo.
    python -c "from daily_email_report import send_daily_report; send_daily_report()"
    
    if errorlevel 1 (
        echo.
        echo ========================================
        echo 错误：邮件发送失败！
        echo.
        echo 请检查：
        echo 1. email_config.py 配置是否正确
        echo 2. 邮箱密码/授权码是否正确
        echo 3. 网络连接是否正常
        echo 4. SMTP服务器设置是否正确
        echo ========================================
    ) else (
        echo.
        echo ========================================
        echo 测试邮件发送成功！
        echo 请检查收件箱: sayanget@yahoo.com
        echo ========================================
    )
) else (
    echo.
    echo 已取消发送
)

echo.
pause
