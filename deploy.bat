@echo off
title Inbound Recorder Deployment Script

echo ========================================
echo   Inbound Recorder 一键部署程序
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python。请先安装Python 3.6或更高版本。
    pause
    exit /b 1
)

echo 检测到Python环境...
echo.

REM 创建备份目录
echo 创建备份...
if not exist "backup_%date:~0,4%_%date:~5,2%_%date:~8,2%" mkdir "backup_%date:~0,4%_%date:~5,2%_%date:~8,2%"
xcopy "single_app.py" "backup_%date:~0,4%_%date:~5,2%_%date:~8,2%\" /Y >nul
if exist "inbound.db" xcopy "inbound.db" "backup_%date:~0,4%_%date:~5,2%_%date:~8,2%\" /Y >nul
xcopy "static\*.*" "backup_%date:~0,4%_%date:~5,2%_%date:~8,2%\" /Y >nul
echo 备份完成.
echo.

REM 安装依赖
echo 安装所需依赖包...
pip install --upgrade pip >nul 2>&1
pip install flask pytz openpyxl pyinstaller >nul 2>&1
echo 依赖包安装完成.
echo.

REM 清理之前的构建
echo 清理之前的构建...
if exist "build" rmdir /s /q "build" >nul 2>&1
if exist "dist" rmdir /s /q "dist" >nul 2>&1
echo 清理完成.
echo.

REM 构建可执行文件
echo 开始构建可执行文件...
python -m PyInstaller --onefile --add-data "static;static" --hidden-import=openpyxl --hidden-import=pytz single_app.py > build.log 2>&1
if %errorlevel% neq 0 (
    echo 构建过程中出现错误，请查看 build.log 文件了解详情。
    pause
    exit /b 1
)
echo 可执行文件构建完成.
echo.

REM 更新部署包
echo 更新部署包...
if not exist "deployment_package" mkdir "deployment_package"
copy "dist\single_app.exe" "deployment_package\" /Y >nul
copy "inbound.db" "deployment_package\" /Y >nul

REM 创建运行脚本
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo echo ========================================
    echo echo   Inbound Recorder 应用启动器
    echo echo ========================================
    echo echo.
    echo echo 启动 Inbound Recorder 应用...
    echo echo.
    echo echo 请在浏览器中访问以下地址:
    echo echo http://localhost:8080
    echo echo.
    echo echo 按 Ctrl+C 可停止应用
    echo echo.
    echo echo ========================================
    echo single_app.exe
) > deployment_package\启动应用.bat
echo 部署包更新完成.
echo.

echo ========================================
echo 部署完成!
echo.
echo 部署包位置: deployment_package\
echo 运行应用请执行: deployment_package\启动应用.bat
echo.
echo 访问地址: http://localhost:8080
echo ========================================

pause