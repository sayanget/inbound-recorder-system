@echo off
chcp 65001 > nul
setlocal ENABLEDELAYEDEXPANSION

REM =========================================================
REM 流向分布工具 — Build Script
REM 依赖: Python 3.9+；依赖包由本脚本自动安装
REM 产物: dist\流向分布工具.exe（自带图标）
REM =========================================================

cd /d "%~dp0"

set "SCRIPT_DIR=%~dp0"
set "DST_HTML=%SCRIPT_DIR%route-distribution.html"
set "REPO_HTML=%SCRIPT_DIR%..\..\static\route-distribution.html"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"

echo ===============================================================
echo  脚本目录 : %SCRIPT_DIR%
echo ===============================================================
echo.

echo [0/6] 检查 Python 并安装依赖

REM 优先使用同目录下的便携 Python（由 init_portable.bat 创建）
set "PORTABLE_PY=%SCRIPT_DIR%portable\python.exe"
if exist "%PORTABLE_PY%" (
    echo    检测到便携 Python: %PORTABLE_PY%
    set "PY=%PORTABLE_PY%"
    set "PY_MODE=portable"
) else (
    where python > nul 2>&1
    if errorlevel 1 (
        echo    [!] 未检测到 python，且没有便携 Python 环境
        echo.
        echo    解决办法二选一：
        echo      A^) 双击 init_portable.bat 创建便携 Python（推荐，零污染）
        echo      B^) 安装系统 Python 3.9+（勾选 Add to PATH）：
        echo         https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY=python"
    set "PY_MODE=system"
)

for /f "tokens=*" %%v in ('"%PY%" --version 2^>^&1') do set "PYVER=%%v"
echo    %PYVER%  [模式: %PY_MODE%]

if not exist "%REQ_FILE%" (
    echo    [!] 未找到 requirements.txt: %REQ_FILE%
    pause
    exit /b 1
)

REM 便携模式里如果已经有 .ready 标志且所有依赖完好，可跳过 pip
if "%PY_MODE%"=="portable" if exist "%SCRIPT_DIR%portable\.ready" (
    "%PY%" -c "import flask, requests, PyInstaller, PIL" > nul 2>&1
    if not errorlevel 1 (
        echo    便携环境依赖完好，跳过 pip install
        goto :deps_done
    )
)

REM 升级 pip（静默，失败不退出）
"%PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check > nul 2>&1

echo    安装/更新依赖（flask / requests / pyinstaller / Pillow）...
"%PY%" -m pip install -r "%REQ_FILE%" --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo    [!] 依赖安装失败。可能原因:
    echo        - 无网络；企业内网可配 pip 镜像：
    echo            %PY% -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    echo        - Python 过旧；需 3.9+
    pause
    exit /b 1
)

:deps_done
echo    OK 依赖就绪
echo.

echo [1/6] 准备 route-distribution.html
REM 策略：
REM   1) 如果脚本所在仓库 static\route-distribution.html 存在，优先同步（开发者场景）
REM   2) 否则用本地同目录已有的 route-distribution.html（独立打包场景）
REM   3) 都没有才报错
if exist "%REPO_HTML%" (
    echo    发现仓库源文件 —— 同步最新版
    echo    来源: %REPO_HTML%
    copy /Y "%REPO_HTML%" "%DST_HTML%" > "%TEMP%\rd_copy.log" 2>&1
    if errorlevel 1 (
        echo    [info] cmd copy 失败，改用 PowerShell:
        type "%TEMP%\rd_copy.log"
        powershell -NoProfile -Command "Copy-Item -LiteralPath '%REPO_HTML%' -Destination '%DST_HTML%' -Force"
        if errorlevel 1 (
            echo    [!] PowerShell 也失败，放弃
            pause
            exit /b 1
        )
    )
    echo    OK: %DST_HTML%
) else (
    if exist "%DST_HTML%" (
        echo    未找到仓库源 %REPO_HTML%
        echo    使用本地同目录已有文件：%DST_HTML%
    ) else (
        echo.
        echo    [!] 既未找到仓库源，也未在本目录找到 route-distribution.html
        echo        请把 route-distribution.html 放到：
        echo           %SCRIPT_DIR%
        echo        或在仓库 static\ 下保留它。
        pause
        exit /b 1
    )
)

echo [2/6] 生成/确认 icon.ico
if not exist "%SCRIPT_DIR%icon.ico" (
    "%PY%" "%SCRIPT_DIR%gen_icon.py"
    if errorlevel 1 (
        echo    [!] 图标生成失败，将无图标继续构建
    )
) else (
    echo    icon.ico 已存在，跳过生成（删除后可重新生成）
)

echo [3/6] 检查 PyInstaller
"%PY%" -m PyInstaller --version > nul 2>&1
if errorlevel 1 (
    echo    [!] PyInstaller 不可用（刚才 pip 安装应该已装上，异常）
    echo        尝试重新安装: "%PY%" -m pip install --force-reinstall pyinstaller
    pause
    exit /b 1
)
set "PYI_CMD=%PY% -m PyInstaller"
echo    使用: %PYI_CMD%

echo [4/6] 清理上次构建产物
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "流向分布工具.spec" del /f /q "流向分布工具.spec"

echo [5/6] 构建单文件 exe
set "ICON_ARG="
if exist "%SCRIPT_DIR%icon.ico" set "ICON_ARG=--icon icon.ico"

%PYI_CMD% ^
    --onefile ^
    --name "流向分布工具" ^
    --add-data "route-distribution.html;." ^
    --add-data "icon.ico;." ^
    --hidden-import flask ^
    --hidden-import requests ^
    --console ^
    %ICON_ARG% ^
    app.py

if errorlevel 1 (
    echo.
    echo [X] 构建失败，请查看上面日志。
    pause
    exit /b 1
)

echo [6/6] 收尾：把 icon.ico 复制到 dist\（供快捷方式引用）
if exist "%SCRIPT_DIR%icon.ico" copy /Y "%SCRIPT_DIR%icon.ico" "%SCRIPT_DIR%dist\icon.ico" > nul

echo.
echo =========================================================
echo  构建成功!
echo  产物: %SCRIPT_DIR%dist\流向分布工具.exe
echo.
echo  创建桌面快捷方式 (带图标):
echo     create_shortcut.bat
echo.
echo  修改后端地址的四种方式 (任选一种):
echo    0. 运行后在浏览器里进 /setup 页一键扫描 (推荐)
echo    A. exe 同目录编辑 config.txt
echo    B. 设置环境变量 ROUTE_DIST_BACKEND
echo    C. 流向分布工具.exe --backend http://x.x.x.x:port
echo =========================================================
pause
