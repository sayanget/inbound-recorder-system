@echo off
chcp 65001 > nul
setlocal

REM =========================================================
REM 在桌面上创建"流向分布工具"的快捷方式（带图标）
REM 默认指向同目录 dist\流向分布工具.exe
REM 用法：
REM   create_shortcut.bat                          ← 当前用户桌面
REM   create_shortcut.bat /public                  ← 公共桌面（所有用户可见，需管理员）
REM   create_shortcut.bat "D:\Tools\..."           ← 指定 exe 路径
REM =========================================================

cd /d "%~dp0"

set "TARGET=%~dp0dist\流向分布工具.exe"
set "ICON=%~dp0dist\icon.ico"
set "SHORTCUT_NAME=流向分布工具.lnk"
set "DESK=%USERPROFILE%\Desktop"

REM 支持传参
if /i "%~1"=="/public" (
    set "DESK=%PUBLIC%\Desktop"
    shift
)
if not "%~1"=="" (
    if exist "%~1" set "TARGET=%~1"
)

if not exist "%TARGET%" (
    echo [X] 未找到 exe: %TARGET%
    echo     请先执行 build.bat 构建，或传入 exe 路径：
    echo         create_shortcut.bat "C:\full\path\to\流向分布工具.exe"
    pause
    exit /b 1
)

if not exist "%ICON%" (
    REM 回退：用源码目录的 icon.ico；再不行就让 Windows 从 exe 里抽取
    if exist "%~dp0icon.ico" (
        set "ICON=%~dp0icon.ico"
    ) else (
        set "ICON=%TARGET%"
    )
)

echo 目标:   %TARGET%
echo 图标:   %ICON%
echo 桌面:   %DESK%
echo 名称:   %SHORTCUT_NAME%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$sc = $ws.CreateShortcut([IO.Path]::Combine('%DESK%', '%SHORTCUT_NAME%'));" ^
    "$sc.TargetPath = '%TARGET%';" ^
    "$sc.WorkingDirectory = [IO.Path]::GetDirectoryName('%TARGET%');" ^
    "$sc.IconLocation = '%ICON%,0';" ^
    "$sc.Description = '流向分布数据表（本地单机版）';" ^
    "$sc.WindowStyle = 1;" ^
    "$sc.Save();" ^
    "Write-Host '[ok] 快捷方式已创建:' ([IO.Path]::Combine('%DESK%', '%SHORTCUT_NAME%'))"

if errorlevel 1 (
    echo [X] 创建快捷方式失败
    pause
    exit /b 1
)

echo.
echo =========================================================
echo  已在桌面生成: %SHORTCUT_NAME%
echo  双击即可启动。
echo =========================================================
pause
