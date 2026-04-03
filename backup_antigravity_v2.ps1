param(
    [string]$BackupPath = "D:\antigravity_backup",
    [switch]$SkipHistory
)

$ErrorActionPreference = "Stop"
$backupDate = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "${BackupPath}_${backupDate}"

Write-Host "========================================"
Write-Host "  Antigravity Backup Tool"
Write-Host "========================================"
Write-Host ""

# Create backup directory
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Host "[1/3] Created backup directory: $backupDir"
Write-Host ""

# Backup global .agent
Write-Host "[2/3] Backing up global skills and workflows..."
$globalAgentPath = "c:\Users\$env:USERNAME\.agent"
if (Test-Path $globalAgentPath) {
    $destPath = Join-Path $backupDir ".agent"
    Copy-Item -Path $globalAgentPath -Destination $destPath -Recurse -Force
    $skillCount = (Get-ChildItem "$destPath\skills" -Directory -ErrorAction SilentlyContinue).Count
    Write-Host "  - Backed up $skillCount global skills"
}
else {
    Write-Host "  - Global .agent not found"
}

# Backup project .agent
$projectAgentPath = "d:\project\inbound_python_source\.agent"
if (Test-Path $projectAgentPath) {
    $destPath = Join-Path $backupDir "project_.agent"
    Copy-Item -Path $projectAgentPath -Destination $destPath -Recurse -Force
    $projectSkillCount = (Get-ChildItem "$destPath\skills" -Directory -ErrorAction SilentlyContinue).Count
    Write-Host "  - Backed up $projectSkillCount project skills"
}
else {
    Write-Host "  - Project .agent not found"
}
Write-Host ""

# Backup .gemini
Write-Host "[3/3] Backing up Antigravity config and history..."
$geminiPath = "c:\Users\$env:USERNAME\.gemini"
if (Test-Path $geminiPath) {
    if ($SkipHistory) {
        $destPath = Join-Path $backupDir ".gemini"
        New-Item -ItemType Directory -Path $destPath -Force | Out-Null
        Get-ChildItem $geminiPath -File | Copy-Item -Destination $destPath -Force
        Write-Host "  - Backed up config only (skipped history)"
    }
    else {
        $destPath = Join-Path $backupDir ".gemini"
        Copy-Item -Path $geminiPath -Destination $destPath -Recurse -Force
        $size = (Get-ChildItem $destPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  - Backed up config and history ($([math]::Round($size, 2)) MB)"
    }
}
else {
    Write-Host "  - .gemini not found"
}
Write-Host ""

# Compress
Write-Host "Compressing backup..."
$zipPath = "${backupDir}.zip"
Compress-Archive -Path $backupDir -DestinationPath $zipPath -Force
$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host ""
Write-Host "========================================"
Write-Host "  Backup Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Backup file: $zipPath"
Write-Host "Size: $([math]::Round($zipSize, 2)) MB"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Copy the zip file to your new machine"
Write-Host "2. Run: .\restore_antigravity.ps1 -BackupZipPath 'path\to\backup.zip'"
Write-Host ""

$response = Read-Host "Delete uncompressed folder to save space? (y/N)"
if ($response -eq 'y' -or $response -eq 'Y') {
    Remove-Item -Path $backupDir -Recurse -Force
    Write-Host "Deleted uncompressed folder"
}
