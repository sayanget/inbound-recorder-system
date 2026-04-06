# 本地怎样，GitHub 就怎样：暂存所有变更 -> 提交（若有）-> 强制推送 origin/main
# 适用：仅你本人维护该仓库、无他人向 main 推送时使用 force 无协作风险。
# 用法: .\scripts\sync_github_full.ps1 [-Message "提交说明"]
# 需在仓库根目录执行，或先 cd 到项目根目录。

param(
    [string]$Message = "sync: local snapshot $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

$ErrorActionPreference = "Stop"
# 脚本位于 scripts/，仓库根为上一级目录
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".git")) {
    Write-Error "Not a git repository: $root"
    exit 1
}

git add -A
$status = git status --porcelain
if ($status) {
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git commit failed"
        exit 1
    }
} else {
    Write-Host "Nothing to commit; pushing current HEAD as-is."
}

git push --force origin main
if ($LASTEXITCODE -ne 0) {
    Write-Error "git push --force failed"
    exit 1
}

Write-Host "Done: origin/main matches local main."
