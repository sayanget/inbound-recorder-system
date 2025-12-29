@echo off
REM 备份inbound_python_source项目
REM 创建带时间戳的备份文件夹

echo ========================================
echo 备份 inbound_python_source 项目
echo ========================================

REM 获取当前日期和时间 (格式: YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set timestamp=%datetime:~0,8%_%datetime:~8,6%

REM 设置备份目录名称
set BACKUP_DIR=backup_%timestamp%

echo.
echo 创建备份目录: %BACKUP_DIR%
mkdir %BACKUP_DIR%

echo.
echo 正在复制文件...
echo.

REM 复制主要的Python文件
xcopy /Y /Q single_app.py %BACKUP_DIR%\
xcopy /Y /Q daily_email_report.py %BACKUP_DIR%\
xcopy /Y /Q setup_email_config.py %BACKUP_DIR%\
xcopy /Y /Q email_config.py %BACKUP_DIR%\ 2>nul

REM 复制数据库文件
xcopy /Y /Q inbound.db %BACKUP_DIR%\ 2>nul

REM 复制静态文件夹
xcopy /E /I /Y /Q static %BACKUP_DIR%\static\

REM 复制配置和文档文件
xcopy /Y /Q requirements.txt %BACKUP_DIR%\
xcopy /Y /Q *.md %BACKUP_DIR%\ 2>nul
xcopy /Y /Q *.bat %BACKUP_DIR%\ 2>nul

echo.
echo ========================================
echo 备份完成！
echo 备份位置: %CD%\%BACKUP_DIR%
echo ========================================
echo.

pause
