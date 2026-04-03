param(
    [Parameter(Mandatory = $true)]
    [string]$BackupZipPath,
    [switch]$SkipHistory
)

$ErrorActionPreference = "Stop"

Write-Host "========================================"
Write-Host "  Antigravity Restore Tool"
Write-Host "========================================"
Write-Host ""

# Check backup file exists
if (-not (Test-Path $BackupZipPath)) {
    Write-Host "Error: Backup file not found: $BackupZipPath" -ForegroundColor Red
    exit 1
}

# Extract to temp
Write-Host "[1/3] Extracting backup..."
$tempDir = Join-Path $env:TEMP "antigravity_restore_$(Get-Date -Format 'yyyyMMddHHmmss')"
Expand-Archive -Path $BackupZipPath -DestinationPath $tempDir -Force

$backupDir = Get-ChildItem $tempDir -Directory | Select-Object -First 1
if (-not $backupDir) {
    Write-Host "Error: Invalid backup file format" -ForegroundColor Red
    exit 1
}
$backupPath = $backupDir.FullName
Write-Host "  - Extracted to temp directory"
Write-Host ""

# Restore global .agent
Write-Host "[2/3] Restoring global skills..."
$sourceAgentPath = Join-Path $backupPath ".agent"
$targetAgentPath = "c:\Users\$env:USERNAME\.agent"

if (Test-Path $sourceAgentPath) {
    # Backup existing if present
    if (Test-Path $targetAgentPath) {
        $backupExisting = "${targetAgentPath}_backup_$(Get-Date -Format 'yyyyMMddHHmmss')"
        Write-Host "  - Backing up existing config to: $backupExisting"
        Copy-Item -Path $targetAgentPath -Destination $backupExisting -Recurse -Force
    }
    
    # Restore
    Copy-Item -Path $sourceAgentPath -Destination $targetAgentPath -Recurse -Force
    $skillCount = (Get-ChildItem "$targetAgentPath\skills" -Directory -ErrorAction SilentlyContinue).Count
    Write-Host "  - Restored $skillCount global skills to $targetAgentPath"
}
else {
    Write-Host "  - No global .agent found in backup"
}
Write-Host ""

# Restore .gemini
Write-Host "[3/3] Restoring Antigravity config and history..."
$sourceGeminiPath = Join-Path $backupPath ".gemini"
$targetGeminiPath = "c:\Users\$env:USERNAME\.gemini"

if (Test-Path $sourceGeminiPath) {
    if ($SkipHistory) {
        Write-Host "  - Restoring config only (skipping history)"
        New-Item -ItemType Directory -Path $targetGeminiPath -Force | Out-Null
        Get-ChildItem $sourceGeminiPath -File | Copy-Item -Destination $targetGeminiPath -Force
    }
    else {
        # Backup existing if present
        if (Test-Path $targetGeminiPath) {
            $backupExisting = "${targetGeminiPath}_backup_$(Get-Date -Format 'yyyyMMddHHmmss')"
            Write-Host "  - Backing up existing config to: $backupExisting"
            Copy-Item -Path $targetGeminiPath -Destination $backupExisting -Recurse -Force
        }
        
        Write-Host "  - Restoring config and history (may take a while)..."
        Copy-Item -Path $sourceGeminiPath -Destination $targetGeminiPath -Recurse -Force
        $size = (Get-ChildItem $targetGeminiPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  - Restored config and history ($([math]::Round($size, 2)) MB) to $targetGeminiPath"
    }
}
else {
    Write-Host "  - No .gemini found in backup"
}
Write-Host ""

# Cleanup temp
Write-Host "Cleaning up temporary files..."
Remove-Item -Path $tempDir -Recurse -Force
Write-Host ""

# Complete
Write-Host "========================================"
Write-Host "  Restore Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Restored to:"
Write-Host "  - Global skills: $targetAgentPath"
Write-Host "  - Config/history: $targetGeminiPath"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart Antigravity"
Write-Host "  2. Verify skills are loaded correctly"
Write-Host ""
