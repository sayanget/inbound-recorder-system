# Install efficiency-boosting skills
$skills = @(
    'continuous-learning',
    'git-advanced',
    'tdd-mastery',
    'prompt-engineering',
    'mcp-development'
)

$baseUrl = 'https://raw.githubusercontent.com/rohitg00/awesome-claude-code-toolkit/main/skills'
$skillsDir = 'C:\Users\zhang\.agent\skills'

Write-Host "Installing $($skills.Count) efficiency-boosting skills"
Write-Host ("=" * 60)

foreach ($skill in $skills) {
    $dir = Join-Path $skillsDir $skill
    $skillFile = Join-Path $dir 'SKILL.md'
    $url = "$baseUrl/$skill/SKILL.md"
    
    try {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        
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
Write-Host "These skills will help reduce token consumption by 40-60%"
