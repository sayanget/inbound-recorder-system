# Install recommended skills from awesome-claude-code-toolkit
$skills = @(
    'python-best-practices',
    'database-optimization',
    'react-patterns',
    'frontend-excellence',
    'api-design-patterns',
    'testing-strategies',
    'docker-best-practices',
    'monitoring-observability',
    'performance-optimization',
    'security-hardening'
)

$baseUrl = 'https://raw.githubusercontent.com/rohitg00/awesome-claude-code-toolkit/main/skills'
$skillsDir = 'C:\Users\zhang\.agent\skills'

Write-Host "Installing $($skills.Count) skills to $skillsDir"
Write-Host ("=" * 60)

foreach ($skill in $skills) {
    $dir = Join-Path $skillsDir $skill
    $skillFile = Join-Path $dir 'SKILL.md'
    $url = "$baseUrl/$skill/SKILL.md"
    
    try {
        # Create directory if it doesn't exist
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        
        # Download SKILL.md
        Write-Host "Downloading $skill..." -NoNewline
        Invoke-WebRequest -Uri $url -OutFile $skillFile -ErrorAction Stop
        Write-Host " Installed" -ForegroundColor Green
    }
    catch {
        Write-Host " Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "Installation complete!"
Write-Host "Installed skills location: $skillsDir"
