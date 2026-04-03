# 移除 install_neon_watch_startup.ps1 创建的启动项

$Startup = [Environment]::GetFolderPath("Startup")
$LnkPath = Join-Path $Startup "InboundNeonSync.lnk"
if (Test-Path $LnkPath) {
    Remove-Item $LnkPath -Force
    Write-Host "已删除: $LnkPath"
} else {
    Write-Host "未找到快捷方式: $LnkPath"
}
