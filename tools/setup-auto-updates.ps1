# setup-auto-updates.ps1 (run by "Set up automatic exe updates.bat"): from now on every pull also fetches the newest .exe builds.
# It points this copy of the repo at its .githooks folder (Git's core.hooksPath), then fetches the newest builds right away.
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$done = $false
if (Get-Command git -ErrorAction SilentlyContinue) { git config core.hooksPath .githooks; $done = ($LASTEXITCODE -eq 0) }
if (-not $done) {                                                       # (no git on PATH - e.g. only GitHub Desktop: edit the setting directly)
    $cfg = Join-Path $Root ".git\config"
    $text = Get-Content $cfg -Raw
    if ($text -notmatch "hooksPath") { Add-Content -Path $cfg -Value "`n[core]`n`thooksPath = .githooks" }
}
Write-Host "Automatic exe updates are on: every pull now fetches the newest builds into EXE Build." -ForegroundColor Green
Write-Host ""
& (Join-Path $PSScriptRoot "get-latest-exes.ps1")
