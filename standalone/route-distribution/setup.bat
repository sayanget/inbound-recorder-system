@echo off
chcp 65001 > nul
setlocal ENABLEDELAYEDEXPANSION

REM =========================================================
REM 流向分布工具 — 零基础一键打包
REM  - 假设电脑是刚装完 Windows，什么都没有
REM  - 自动装 Python → 装依赖 → 打包 → 生成桌面快捷方式
REM =========================================================

cd /d "%~dp0"

echo =========================================================
echo  流向分布工具 — 一键环境准备 + 打包
echo  （假设电脑只装了 Windows）
echo =========================================================
echo.
echo  本脚本将依次完成：
echo    [1] 检测 / 自动安装 Python 3.12（当前用户，无需管理员）
echo    [2] 调用 build.bat 装依赖并打包 exe
echo    [3] 询问是否在桌面创建带图标的快捷方式
echo.
echo  预计耗时：首次 3~8 分钟（取决于网速）；之后重复跑仅 30 秒
echo =========================================================
echo.
pause

REM ---------------------------------------------------------
REM Step 1: ensure Python is on PATH
REM ---------------------------------------------------------
echo.
echo [1/3] 检测 Python
where python > nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo    已安装: %%v
    goto :has_python
)

echo    未检测到 Python，开始自动安装 3.12（当前用户模式，不需要管理员）
echo.

REM ---- Method A: winget (Win10 1809+ / Win11 自带) ----
winget --version > nul 2>&1
if not errorlevel 1 (
    echo    [方式 A] winget install Python.Python.3.12
    winget install --id Python.Python.3.12 ^
        --accept-package-agreements --accept-source-agreements ^
        --scope user --silent --disable-interactivity
    if not errorlevel 1 (
        echo    winget 完成
        goto :refresh_path
    )
    echo    winget 失败（错误码 %errorlevel%），改用直接下载
    echo.
)

REM ---- Method B: direct download from python.org ----
set "PY_URL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
set "PY_INSTALLER=%TEMP%\python-3.12-setup.exe"

echo    [方式 B] 从 python.org 下载安装程序
echo       URL: %PY_URL%
echo       临时路径: %PY_INSTALLER%
echo.

powershell -NoProfile -Command ^
    "try {" ^
    "  [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12;" ^
    "  $ProgressPreference = 'SilentlyContinue';" ^
    "  Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing -ErrorAction Stop;" ^
    "  Write-Host ('    下载完成：' + ((Get-Item '%PY_INSTALLER%').Length / 1MB).ToString('F1') + ' MB')" ^
    "} catch {" ^
    "  Write-Host '    下载失败: ' $_.Exception.Message;" ^
    "  exit 1" ^
    "}"
if errorlevel 1 (
    echo.
    echo    [!] 下载失败——可能无网络，或被防火墙 / 公司代理拦截
    echo.
    echo        请手动完成以下两步任一：
    echo        1^) 去 https://www.python.org/downloads/ 下载 Python 3.9+，
    echo           安装时勾选 "Add python.exe to PATH"，然后重新双击 setup.bat
    echo        2^) 用公司镜像：https://mirrors.aliyun.com/python/ 或内网 FTP
    echo.
    pause
    exit /b 1
)

echo    运行安装程序（静默，仅当前用户，不需要管理员）...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=0 Include_test=0 SimpleInstall=1
set PY_INSTALL_RC=%errorlevel%
del "%PY_INSTALLER%" > nul 2>&1
if %PY_INSTALL_RC% neq 0 (
    echo    [!] Python 安装程序返回 %PY_INSTALL_RC%
    echo        请右键 setup.bat → 以管理员身份运行，再试一次
    pause
    exit /b 1
)
echo    Python 已安装

:refresh_path
echo.
echo    刷新 PATH 环境变量...
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH','User')"`) do set "PATH=%%p"

where python > nul 2>&1
if errorlevel 1 (
    echo    [!] 安装完成但本窗口仍找不到 python
    echo        请关闭本窗口，重新双击 setup.bat（打开新窗口就能找到了）
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo    Python 就绪: %%v

:has_python
echo.

REM ---------------------------------------------------------
REM Step 2: 可选配 pip 镜像（国内网络更快）
REM ---------------------------------------------------------
echo    测试 pypi.org 连通性...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { $r = Test-NetConnection pypi.org -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue; if ($r) { exit 0 } else { exit 1 } } catch { exit 1 }" > nul 2>&1
if errorlevel 1 (
    echo    pypi.org 不可达，为当前用户配置清华镜像
    python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple > nul 2>&1
) else (
    echo    pypi.org 可达，使用默认源
)

REM ---------------------------------------------------------
REM Step 3: call build.bat (it handles pip install + PyInstaller)
REM ---------------------------------------------------------
echo.
echo [2/3] 调用 build.bat 装依赖并打包...
echo =========================================================
call "%~dp0build.bat"
set BUILD_RC=%errorlevel%
if %BUILD_RC% neq 0 (
    echo.
    echo [X] 打包失败（错误码 %BUILD_RC%），详见上方日志
    pause
    exit /b %BUILD_RC%
)

REM ---------------------------------------------------------
REM Step 4: offer to create desktop shortcut
REM ---------------------------------------------------------
if not exist "%~dp0dist\流向分布工具.exe" (
    echo.
    echo [!] 预期产物不存在: %~dp0dist\流向分布工具.exe
    pause
    exit /b 1
)

echo.
echo [3/3] 桌面快捷方式
choice /C YN /M "  在桌面创建带图标的快捷方式？(Y=是 N=否)"
if errorlevel 2 goto :done
call "%~dp0create_shortcut.bat"

:done
echo.
echo =========================================================
echo  全部完成！
echo.
echo  exe 产物: %~dp0dist\流向分布工具.exe
echo  双击运行；首次启动会自动探测后端可达性，不可达时弹设置页。
echo =========================================================
pause
