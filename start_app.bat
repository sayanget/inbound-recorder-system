@echo off
setlocal enabledelayedexpansion

:: 设置标题
title Inbound Recorder Launcher

:: 清屏
cls

echo ========================================
echo      Inbound Recorder 启动器
echo ========================================
echo.

:: 检查是否已构建EXE文件
if exist "dist\single_app.exe" (
    echo [信息] 发现已构建的EXE文件
    set "USE_EXE=1"
) else (
    echo [警告] 未发现EXE文件，将使用Python脚本启动
    echo         如需构建EXE，请运行 build_exe.bat
    set "USE_EXE=0"
)

echo.

:: 检查必要的文件
echo [检查] 正在检查必要文件...
if not exist "single_app.py" (
    echo [错误] 未找到主程序文件 single_app.py
    pause
    exit /b 1
)

if not exist "static" (
    echo [错误] 未找到静态文件目录 static
    pause
    exit /b 1
)

echo [完成] 所有必需文件均已找到
echo.

:: 显示启动选项
echo ========================================
echo 启动选项:
echo ========================================
if "!USE_EXE!"=="1" (
    echo 1. 使用EXE文件启动 (推荐)
    echo 2. 使用Python脚本启动
    echo 3. 重新构建EXE文件
    echo 4. 退出
) else (
    echo 1. 使用Python脚本启动
    echo 2. 构建EXE文件
    echo 3. 退出
)

echo.

:choice
if "!USE_EXE!"=="1" (
    set /p choice=请选择操作 (1-4): 
) else (
    set /p choice=请选择操作 (1-3): 
)

:: 验证用户输入
if "!USE_EXE!"=="1" (
    if "!choice!"=="1" goto start_exe
    if "!choice!"=="2" goto start_py
    if "!choice!"=="3" goto build_exe
    if "!choice!"=="4" goto exit_script
) else (
    if "!choice!"=="1" goto start_py
    if "!choice!"=="2" goto build_exe
    if "!choice!"=="3" goto exit_script
)

echo 无效的选择，请重新输入。
goto choice

:start_exe
echo.
echo [启动] 正在使用EXE文件启动应用...
echo.
echo 请在浏览器中访问以下地址:
echo http://localhost:8080
echo.
echo 按 Ctrl+C 可停止应用
echo.
echo ========================================
cd /d "%~dp0"
dist\single_app.exe
goto end

:start_py
echo.
echo [启动] 正在使用Python脚本启动应用...
echo.
echo 请在浏览器中访问以下地址:
echo http://localhost:8080
echo.
echo 按 Ctrl+C 可停止应用
echo.
echo ========================================
cd /d "%~dp0"
python single_app.py
goto end

:build_exe
echo.
echo [构建] 正在构建EXE文件...
echo.
cd /d "%~dp0"

:: 检查是否安装了PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装PyInstaller...
    python -m pip install PyInstaller
    if errorlevel 1 (
        echo [错误] PyInstaller安装失败
        pause
        goto choice
    )
)

echo [构建] 开始构建EXE文件...
python -m PyInstaller --onefile --add-data "static;static" single_app.py

if errorlevel 1 (
    echo [错误] EXE构建失败
    pause
) else (
    echo [完成] EXE构建成功，文件位于 dist\single_app.exe
)

echo.
pause
goto choice

:exit_script
echo.
echo 感谢使用 Inbound Recorder!
echo.
pause
exit /b 0

:end
echo.
echo 应用已停止运行。
echo.
pause