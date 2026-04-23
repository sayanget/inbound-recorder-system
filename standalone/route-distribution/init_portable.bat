@echo off
chcp 65001 > nul
setlocal ENABLEDELAYEDEXPANSION

REM =========================================================
REM 流向分布工具 — 便携 Python 环境准备
REM   开发者一次性运行，创建 portable\ 子目录，把 Python + 所有
REM   依赖都装进去。之后整个文件夹可以直接 zip 分发，接收方
REM   解压 → 双击 build.bat → 不装任何东西就能打出 exe。
REM =========================================================

cd /d "%~dp0"
set "SCRIPT_DIR=%~dp0"
set "PORTABLE_DIR=%SCRIPT_DIR%portable"
set "PY_VER=3.12.7"
set "PY_EMBED_URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"

echo =========================================================
echo  构建便携 Python 环境（一次性）
echo  目标目录: %PORTABLE_DIR%
echo  Python  : %PY_VER% (embeddable amd64)
echo =========================================================
echo.

if exist "%PORTABLE_DIR%\python.exe" (
    echo 已检测到 portable\python.exe
    choice /C YN /M "  要完全删除重建吗？(N=保留目录，只更新 pip 依赖)"
    if errorlevel 2 goto :install_deps
    echo 删除旧目录 ...
    rmdir /s /q "%PORTABLE_DIR%" 2> nul
)

REM ----------------------------------------------------------
REM 1) 下载并解压 Python embeddable zip
REM ----------------------------------------------------------
echo [1/4] 下载 Python embeddable
set "ZIP=%TEMP%\py-embed-%PY_VER%.zip"
if exist "%ZIP%" del "%ZIP%"

powershell -NoProfile -Command ^
    "try {" ^
    "  [Net.ServicePointManager]::SecurityProtocol = 'Tls12';" ^
    "  $ProgressPreference = 'SilentlyContinue';" ^
    "  Invoke-WebRequest -Uri '%PY_EMBED_URL%' -OutFile '%ZIP%' -UseBasicParsing -ErrorAction Stop;" ^
    "  $sz = (Get-Item '%ZIP%').Length / 1MB;" ^
    "  Write-Host ('    下载完成: ' + $sz.ToString('F1') + ' MB')" ^
    "} catch {" ^
    "  Write-Host '    下载失败: ' $_.Exception.Message;" ^
    "  exit 1" ^
    "}"
if errorlevel 1 (
    echo    [!] 下载失败。公司内网请手动下载：
    echo        %PY_EMBED_URL%
    echo        保存到 %ZIP% 后重新运行本脚本
    pause
    exit /b 1
)

echo [2/4] 解压到 %PORTABLE_DIR%
if not exist "%PORTABLE_DIR%" mkdir "%PORTABLE_DIR%"
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%ZIP%' -DestinationPath '%PORTABLE_DIR%' -Force"
if errorlevel 1 (
    echo    [!] 解压失败
    pause
    exit /b 1
)
del "%ZIP%" > nul 2>&1

REM ----------------------------------------------------------
REM 2) 修改 python312._pth: 启用 site-packages
REM    embeddable Python 默认注释掉 'import site'，导致 pip 装
REM    的包不会被识别。我们改成启用状态。
REM ----------------------------------------------------------
echo [3/4] 配置 pythonXX._pth
for %%f in ("%PORTABLE_DIR%\python*._pth") do (
    echo     修改: %%f
    powershell -NoProfile -Command ^
        "$p='%%f';" ^
        "$c=Get-Content $p;" ^
        "$c = $c -replace '^#\s*import\s+site','import site';" ^
        "if ($c -notcontains 'import site') { $c += 'import site' };" ^
        "Set-Content $p -Value $c -Encoding ASCII"
)

REM ----------------------------------------------------------
REM 3) 下载 get-pip.py 引导 pip
REM ----------------------------------------------------------
echo     下载 get-pip.py
powershell -NoProfile -Command ^
    "try {" ^
    "  [Net.ServicePointManager]::SecurityProtocol = 'Tls12';" ^
    "  $ProgressPreference = 'SilentlyContinue';" ^
    "  Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%PORTABLE_DIR%\get-pip.py' -UseBasicParsing -ErrorAction Stop" ^
    "} catch {" ^
    "  Write-Host '    下载 get-pip.py 失败: ' $_.Exception.Message;" ^
    "  exit 1" ^
    "}"
if errorlevel 1 (
    pause
    exit /b 1
)

"%PORTABLE_DIR%\python.exe" "%PORTABLE_DIR%\get-pip.py" --no-warn-script-location
if errorlevel 1 (
    echo    [!] get-pip 引导失败
    pause
    exit /b 1
)
del "%PORTABLE_DIR%\get-pip.py" > nul 2>&1

:install_deps
echo.
echo [4/4] 在便携 Python 里安装依赖
if not exist "%SCRIPT_DIR%requirements.txt" (
    echo    [!] 没找到 requirements.txt
    pause
    exit /b 1
)

REM 测试 pypi 连通性；不通则自动切清华镜像
powershell -NoProfile -Command ^
    "$ProgressPreference='SilentlyContinue';" ^
    "try { $r = Test-NetConnection pypi.org -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue;" ^
    "      if ($r) { exit 0 } else { exit 1 } } catch { exit 1 }" > nul 2>&1
if errorlevel 1 (
    echo    pypi.org 不可达，使用清华镜像
    set "PIP_EXTRA=-i https://pypi.tuna.tsinghua.edu.cn/simple"
) else (
    set "PIP_EXTRA="
)

"%PORTABLE_DIR%\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt" --disable-pip-version-check %PIP_EXTRA%
if errorlevel 1 (
    echo    [!] pip 安装依赖失败
    pause
    exit /b 1
)

REM 写一个标志文件，方便后续脚本识别
> "%PORTABLE_DIR%\.ready" echo OK

REM 用 PowerShell 算下整个 portable\ 文件夹有多大（失败也没关系）
set "PSIZE=?"
for /f "usebackq delims=" %%s in (`powershell -NoProfile -Command "try { '{0:F1} MB' -f ((Get-ChildItem -Recurse -LiteralPath '%PORTABLE_DIR%' -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB) } catch { '?' }"`) do set "PSIZE=%%s"

echo.
echo =========================================================
echo  便携 Python 环境就绪!
echo  目录: %PORTABLE_DIR%
echo  大小: %PSIZE%
echo.
echo  下一步任选:
echo    - 本机打包: 双击 build.bat
echo    - 分发给别人:
echo        1. zip 整个 route-distribution 文件夹 （含 portable 子目录）
echo        2. 接收方解压后双击 build.bat
echo           不需要装 Python，不需要联网
echo =========================================================
pause
