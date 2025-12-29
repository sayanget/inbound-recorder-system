@echo off
chcp 65001 >nul
echo.
echo ==========================================
echo Inbound Recorder 一键构建运行包制作工具
echo ==========================================
echo.

REM 检查是否安装了PyInstaller
echo 正在检查PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller 未安装，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo PyInstaller 安装失败，请手动安装后再运行此脚本
        pause
        exit /b 1
    )
)

echo.
echo 开始构建单文件可执行程序...
echo.

REM 使用PyInstaller直接构建，使用指定图标
echo 正在构建应用程序...
pyinstaller --onefile --windowed --name "InboundRecorder" --icon "in.ico" --add-data "static;static" --add-data "inbound.db;." --add-data "DEPLOYMENT.md;." --add-data "DEPLOYMENT_FULL.md;." --hidden-import "openpyxl" --hidden-import "pytz" --hidden-import "sqlite3" --clean "single_app.py"

if errorlevel 1 (
    echo.
    echo 构建失败！
    pause
    exit /b 1
)

echo.
echo 构建完成！
echo.

REM 创建部署包
echo 正在创建部署包...
if exist "dist_package" rmdir /s /q "dist_package"
mkdir "dist_package"

if exist "dist\InboundRecorder.exe" (
    copy "dist\InboundRecorder.exe" "dist_package\" >nul
    echo 已复制 InboundRecorder.exe
)

if exist "inbound.db" (
    copy "inbound.db" "dist_package\" >nul
    echo 已复制 inbound.db
)

if exist "DEPLOYMENT.md" (
    copy "DEPLOYMENT.md" "dist_package\" >nul
    echo 已复制 DEPLOYMENT.md
)

if exist "DEPLOYMENT_FULL.md" (
    copy "DEPLOYMENT_FULL.md" "dist_package\" >nul
    echo 已复制 DEPLOYMENT_FULL.md
)

REM 复制静态文件目录
if exist "static" (
    xcopy "static" "dist_package\static\" /E /I /Y >nul
    echo 已复制 static 目录
)

echo.
echo 创建一键启动批处理文件...
echo @echo off > "dist_package\run_inbound_recorder.bat"
echo echo 启动 Inbound Recorder... >> "dist_package\run_inbound_recorder.bat"
echo start "" "InboundRecorder.exe" >> "dist_package\run_inbound_recorder.bat"
echo echo. >> "dist_package\run_inbound_recorder.bat"
echo echo 按任意键退出... >> "dist_package\run_inbound_recorder.bat"
echo pause >> "dist_package\run_inbound_recorder.bat"

echo.
echo 创建启动脚本完成！

REM 创建ZIP压缩包
if exist "InboundRecorder_Package.zip" del "InboundRecorder_Package.zip"
powershell -command "Compress-Archive -Path dist_package\* -DestinationPath InboundRecorder_Package.zip" 2>nul
if errorlevel 1 (
    echo PowerShell 压缩失败，尝试使用7-Zip或手动压缩...
    echo 请手动压缩 dist_package 目录为 ZIP 文件
) else (
    echo 成功创建压缩包: InboundRecorder_Package.zip
)

echo.
echo ==========================================
echo 构建打包完成！
echo 生成的文件在 dist_package 目录中
echo 压缩包: InboundRecorder_Package.zip
echo ==========================================
echo.
echo 按任意键退出...
pause