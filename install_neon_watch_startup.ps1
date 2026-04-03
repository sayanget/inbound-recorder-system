# 将「SQLite -> Neon 监听」加入当前用户开机启动（启动文件夹快捷方式）
# 需已配置 neon_sync.env 中的 DATABASE_URL
# 卸载：运行 uninstall_neon_watch_startup.ps1

$ErrorActionPreference = "Stop"
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bat = Join-Path $BaseDir "run_watch_neon_sync.bat"
if (-not (Test-Path $Bat)) {
    Write-Error "未找到: $Bat"
}

$Startup = [Environment]::GetFolderPath("Startup")
$LnkName = "InboundNeonSync.lnk"
$LnkPath = Join-Path $Startup $LnkName

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($LnkPath)
$Sc.TargetPath = $Bat
$Sc.WorkingDirectory = $BaseDir
$Sc.WindowStyle = 1
$Sc.Description = "Inbound: local SQLite changes sync to Neon"
$Sc.Save()

Write-Host "已创建开机启动项: $LnkPath"
Write-Host "重启或注销后生效；也可在开始菜单「启动」文件夹中双击测试。"
