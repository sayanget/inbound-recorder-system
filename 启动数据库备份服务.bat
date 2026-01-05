@echo off
chcp 65001 > nul
echo ============================================================
echo 启动数据库备份服务
echo ============================================================
echo.

REM 检查Python是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

echo 正在启动数据库备份定时任务...
echo.
echo 提示: 
echo - 程序将在后台持续运行
echo - 按 Ctrl+C 可以停止服务
echo - 备份时间在 email_config.py 中配置
echo.
echo ============================================================
echo.

python db_backup_service.py

if errorlevel 1 (
    echo.
    echo 错误: 备份服务启动失败
    echo 请检查:
    echo 1. email_config.py 配置是否正确
    echo 2. inbound.db 数据库文件是否存在
    echo 3. 网络连接是否正常
)

pause
