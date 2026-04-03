@echo off
chcp 65001 >nul
echo ========================================
echo 更新历史记录时长数据
echo ========================================
echo.
echo 此脚本将重新计算所有历史记录的时长
echo 注意: Car和Van不占用道口,不计算时长
echo.
set /p confirm="是否继续? (输入 yes 确认): "
if /i not "%confirm%"=="yes" (
    echo 操作已取消
    pause
    exit /b
)

echo.
echo 开始更新...
echo.

python migrate_duration.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo 更新完成!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo 更新失败,请检查错误信息
    echo ========================================
)

echo.
pause
