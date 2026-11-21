# get-latest-exes.ps1: puts the newest InstantEasel.exe and InstantEaselPro.exe from the Releases page into their EXE Build folders.
# The .exe files are too big to keep in the repo, so each build publishes them as prereleases instead. This runs by itself after
# every GitHub Desktop pull (after "Set up automatic exe updates.bat"), or double-click "Get latest exe.bat" any time.
# It only downloads a build you don't have yet, downloads to a .part file first, and leaves the old .exe alone if anything fails
# (or if the app is open). What it did is written to EXE Build\exe-update.log.
$ErrorActionPreference = "Stop"
$Repo = "StevenCLewis111/Instant-Easel"
$Root = Split-Path -Parent $PSScriptRoot
$Apps = @(
    @{ Tag = "drawing-app-latest"; File = "InstantEasel.exe";    Dir = Join-Path $Root "Instant Easel\EXE Build" },
    @{ Tag = "pro-latest";         File = "InstantEaselPro.exe"; Dir = Join-Path $Root "Instant Easel Pro\EXE Build" }
)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"          # (the progress bar makes downloads in PowerShell 5 very slow)

foreach ($a in $Apps) {
    New-Item -ItemType Directory -Force -Path $a.Dir | Out-Null
    $log = Join-Path $a.Dir "exe-update.log"
    function Note($t) { Write-Host $t; Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $t) }
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/tags/$($a.Tag)" -Headers @{ "User-Agent" = "InstantEasel-updater" }
        $asset = $rel.assets | Where-Object { $_.name -eq $a.File } | Select-Object -First 1
        if (-not $asset) { Note "no $($a.File) on the $($a.Tag) release yet"; continue }
        $stamp = Join-Path $a.Dir ".exe-build"
        $dest = Join-Path $a.Dir $a.File
        $have = if (Test-Path $stamp) { (Get-Content $stamp -Raw).Trim() } else { "" }
        $want = "$($asset.id) $($asset.updated_at)"
        if ($have -eq $want -and (Test-Path $dest)) { Note "$($a.File): already the newest ($($rel.name))"; continue }
        $part = "$dest.part"
        Note "$($a.File): downloading $($rel.name) ($([math]::Round($asset.size / 1MB)) MB)..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $part -UseBasicParsing -Headers @{ "User-Agent" = "InstantEasel-updater" }
        if ((Get-Item $part).Length -ne $asset.size) { Remove-Item $part -Force; throw "the download was incomplete" }
        try { Move-Item -Force $part $dest }
        catch { Note "$($a.File): downloaded, but the app is open - close it and run Get latest exe.bat"; continue }
        Set-Content -Path $stamp -Value $want
        Note "$($a.File): updated to $($rel.name)"
    } catch { Note "$($a.File): couldn't update ($($_.Exception.Message))" }
}
