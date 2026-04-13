# Sync a local Markdown brain repo into gbrain (keyword index). Vector embed is opt-in.
# Prereq: gbrain on PATH (e.g. bun install per https://github.com/garrytan/gbrain )
# Usage:
#   $env:GBRAIN_REPO = "D:\path\to\your-brain-repo"
#   .\scripts\brain_gbrain_sync.ps1
# Or:
#   .\scripts\brain_gbrain_sync.ps1 -BrainRepo "D:\path\to\your-brain-repo"
# Optional: -Embed runs `gbrain embed --stale` (needs OpenAI or patched provider).
# Optional: -Doctor runs gbrain doctor --json at the end.

param(
    [string]$BrainRepo = $env:GBRAIN_REPO,
    [switch]$Embed,
    [switch]$Doctor
)

$ErrorActionPreference = "Stop"

$localDefaults = Join-Path $PSScriptRoot 'brain_gbrain_sync.local.ps1'
if (Test-Path -LiteralPath $localDefaults) {
    . $localDefaults
}
if (-not $BrainRepo) { $BrainRepo = $env:GBRAIN_REPO }

function Get-GbrainExecutable {
    $cmd = Get-Command gbrain -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $bunBin = Join-Path $env:USERPROFILE ".bun\bin\gbrain.exe"
    if (Test-Path -LiteralPath $bunBin) { return $bunBin }
    Write-Error "gbrain not found. Install: bun add -g github:garrytan/gbrain (see https://github.com/garrytan/gbrain )"
    exit 1
}

$GbrainExe = Get-GbrainExecutable

if (-not $BrainRepo -or -not (Test-Path -LiteralPath $BrainRepo -PathType Container)) {
    Write-Error @"
Set the brain repo directory first.
  PowerShell: `$env:GBRAIN_REPO = 'D:\path\to\your-brain-repo'
Or pass: -BrainRepo 'D:\path\to\your-brain-repo'
Current value: '$BrainRepo'
"@
    exit 1
}

$BrainRepo = (Resolve-Path -LiteralPath $BrainRepo).Path
Write-Host "Brain repo: $BrainRepo"
Write-Host "gbrain: $GbrainExe"

Write-Host "gbrain sync --repo ..."
& $GbrainExe sync --repo $BrainRepo
if ($LASTEXITCODE -ne 0) {
    Write-Error "gbrain sync failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

if ($Embed) {
    Write-Host "gbrain embed --stale ..."
    & $GbrainExe embed --stale
    if ($LASTEXITCODE -ne 0) {
        Write-Error "gbrain embed failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Skipping vector embed (keyword search only). Use -Embed to run embed --stale."
}

if ($Doctor) {
    Write-Host "gbrain doctor --json ..."
    & $GbrainExe doctor --json
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "gbrain doctor reported non-zero exit $LASTEXITCODE (see output above)."
    }
}

Write-Host "Done: sync for $BrainRepo$(if ($Embed) { ' + embed --stale' } else { ' (no embed)' })"
