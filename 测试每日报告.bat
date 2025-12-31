@echo off
chcp 65001 > nul
echo ============================================================
echo 测试每日报告（包含数据库备份）
echo ============================================================
echo.

REM 检查Python是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

echo 正在执行每日报告测试...
echo 这将生成Excel报表和数据库备份，并发送测试邮件
echo.
echo ============================================================
echo.

REM 修改daily_email_report.py临时启用立即发送
python -c "exec(open('daily_email_report.py', encoding='utf-8').read().replace('schedule_daily_report()', 'send_daily_report()'))"

echo.
echo ============================================================
echo 测试完成
echo ============================================================
echo.
echo 请检查:
echo 1. 控制台输出是否显示压缩成功
echo 2. 是否收到邮件
echo 3. 邮件是否包含两个附件:
echo    - Excel报表 (daily_report_YYYYMMDD.xlsx)
echo    - 数据库备份 (inbound_backup_YYYYMMDD.zip)
echo.

pause
