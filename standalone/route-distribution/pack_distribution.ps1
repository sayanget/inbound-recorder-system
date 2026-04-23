#
# Build a portable distribution zip of this folder.
#
# Includes the portable/ Python environment so recipients don't need to
# install anything. Excludes build artifacts, caches, logs, and stale zips.
#
# Output: 流向分布工具-便携版-<timestamp>.zip in the parent folder.
#

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
try { $PSStyle.OutputRendering = 'PlainText' } catch { }   # PS7 only

$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$zipName = "流向分布工具-便携版-$stamp.zip"
$zipPath = Join-Path (Split-Path $src -Parent) $zipName

if (-not (Test-Path (Join-Path $src 'portable\python.exe'))) {
    Write-Host "[!] 未找到 portable\python.exe，请先运行 init_portable.bat" -ForegroundColor Red
    exit 1
}

Write-Host "源目录 : $src"
Write-Host "输出   : $zipPath"
Write-Host ""

# Directories and file patterns to exclude from the zip.
$excludeDirs = @('build', 'dist', '__pycache__', '.venv', 'venv', '.git')
$excludeFiles = @('*.log', '*.spec', '*.rar', 'config.txt')

# Enumerate everything we want to include.
Write-Host "[1/2] 枚举要打包的文件 ..."
$items = Get-ChildItem -LiteralPath $src -Recurse -Force -File | Where-Object {
    $rel = $_.FullName.Substring($src.Length).TrimStart('\')
    $parts = $rel -split '\\'
    $inExcludedDir = $false
    foreach ($p in $parts[0..([Math]::Max(0, $parts.Length - 2))]) {
        if ($excludeDirs -contains $p) { $inExcludedDir = $true; break }
    }
    if ($inExcludedDir) { return $false }
    foreach ($pat in $excludeFiles) {
        if ($_.Name -like $pat) { return $false }
    }
    # Exclude the zip itself and any previous ones in parent
    if ($_.FullName -eq $zipPath) { return $false }
    return $true
}

$totalSize = ($items | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("   待打包 {0} 个文件，原始大小 {1:F1} MB" -f $items.Count, $totalSize)

# Stage into a temp folder so Compress-Archive keeps relative paths clean.
Write-Host "[2/2] 压缩..."
$stage = Join-Path $env:TEMP "rd_pack_$stamp"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($f in $items) {
    $rel = $f.FullName.Substring($src.Length).TrimStart('\')
    $dest = Join-Path $stage $rel
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }
    Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
}

# Compress-Archive (built into PS5+). Optimal compression is slow-ish but that's ok.
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal -Force

Remove-Item -Recurse -Force $stage

$zipSize = (Get-Item $zipPath).Length / 1MB

Write-Host ""
Write-Host "========================================================="
Write-Host "  完成!"
Write-Host ("  文件: {0}" -f $zipPath)
Write-Host ("  大小: {0:F1} MB" -f $zipSize)
Write-Host ""
Write-Host "  发给别人后的用法:"
Write-Host "    1. 解压到任意目录 (如 D:\流向分布工具\)"
Write-Host "    2. 双击 build.bat - 自动用便携 Python 打包出 exe"
Write-Host "       (不需要装 Python, 不需要联网)"
Write-Host "    3. 打包完成后双击 create_shortcut.bat 在桌面创建快捷方式"
Write-Host "========================================================="
