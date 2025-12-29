@echo off
chcp 65001 >nul
echo ========================================
echo    安装邮件功能依赖包
echo ========================================
echo.
echo 正在安装 schedule 包...
echo.

pip install schedule

if errorlevel 1 (
    echo.
    echo ========================================
    echo 错误：安装失败！
    echo.
    echo 可能的原因：
    echo 1. Python未安装或未添加到PATH
    echo 2. pip未正确配置
    echo 3. 网络连接问题
    echo.
    echo 请手动运行: pip install schedule
    echo ========================================
) else (
    echo.
    echo ========================================
    echo 安装成功！
    echo.
    echo 下一步：
    echo 1. 运行 '配置邮箱.bat' 配置邮箱信息
    echo 2. 运行 '测试邮件发送.bat' 测试功能
    echo ========================================
)

echo.
pause
