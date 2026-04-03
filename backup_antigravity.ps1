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
Write-Host "[1/2] Created backup directory: $backupDir"
Write-Host ""

# Backup global .agent only (no project files)
Write-Host "[2/2] Backing up global skills and config..."
$globalAgentPath = "c:\Users\zhang\.agent"
if (Test-Path $globalAgentPath) {
    $destPath = Join-Path $backupDir ".agent"
    Copy-Item -Path $globalAgentPath -Destination $destPath -Recurse -Force
    $skillCount = (Get-ChildItem "$destPath\skills" -Directory -ErrorAction SilentlyContinue).Count
    Write-Host "  - Backed up $skillCount global skills"
}
else {
    Write-Host "  - Warning: Global .agent not found at $globalAgentPath"
}

# Backup .gemini
$geminiPath = "c:\Users\zhang\.gemini"
if (Test-Path $geminiPath) {
    if ($SkipHistory) {
        $destPath = Join-Path $backupDir ".gemini"
        New-Item -ItemType Directory -Path $destPath -Force | Out-Null
        Get-ChildItem $geminiPath -File | Copy-Item -Destination $destPath -Force
        Write-Host "  - Backed up config only (skipped history)"
    }
    else {
        $destPath = Join-Path $backupDir ".gemini"
        Write-Host "  - Copying .gemini directory (may take a while)..."
        Copy-Item -Path $geminiPath -Destination $destPath -Recurse -Force
        $size = (Get-ChildItem $destPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  - Backed up config and history ($([math]::Round($size, 2)) MB)"
    }
}
else {
    Write-Host "  - Warning: .gemini not found at $geminiPath"
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
Write-Host "Note: Project files are NOT included (only global skills)"
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
