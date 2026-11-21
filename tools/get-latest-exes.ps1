# get-latest-exes.ps1: puts the newest Instant Easel and Instant Easel Pro builds from the Releases page into their EXE Build folders.
# Each build is an app folder (InstantEasel.exe + _internal\, which holds the app's files and the cut-out AI), published as a zip
# because it's too big to keep in the repo. This runs by itself after every GitHub Desktop pull (after "Set up automatic exe
# updates.bat"), or double-click "Get latest exe.bat" any time.
# It only downloads a build you don't have yet, unpacks it beside the old one first, and only then swaps them; if anything fails,
# or the app is open, the old one stays as it was. Your settings, stickers and pictures in EXE Build are never touched.
# What it did is written to EXE Build\exe-update.log.
$ErrorActionPreference = "Stop"
$Repo = "StevenCLewis111/Instant-Easel"
$Root = Split-Path -Parent $PSScriptRoot
$Apps = @(
    @{ Tag = "drawing-app-latest"; Name = "InstantEasel";    Dir = Join-Path $Root "Instant Easel\EXE Build" },
    @{ Tag = "pro-latest";         Name = "InstantEaselPro"; Dir = Join-Path $Root "Instant Easel Pro\EXE Build" }
)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"          # (the progress bar makes downloads in PowerShell 5 very slow)
Add-Type -AssemblyName System.IO.Compression.FileSystem

foreach ($a in $Apps) {
    New-Item -ItemType Directory -Force -Path $a.Dir | Out-Null
    $log = Join-Path $a.Dir "exe-update.log"
    function Note($t) { Write-Host $t; Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $t) }
    $exe = "$($a.Name).exe"
    $zip = Join-Path $a.Dir ".update.zip"; $new = Join-Path $a.Dir ".update-new"
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/tags/$($a.Tag)" -Headers @{ "User-Agent" = "InstantEasel-updater" }
        $asset = $rel.assets | Where-Object { $_.name -eq "$($a.Name)-windows.zip" } | Select-Object -First 1
        if (-not $asset) { Note "$($exe): no $($a.Name)-windows.zip on the $($a.Tag) release yet"; continue }
        $stamp = Join-Path $a.Dir ".exe-build"
        $dest = Join-Path $a.Dir $exe; $internal = Join-Path $a.Dir "_internal"
        $have = if (Test-Path $stamp) { (Get-Content $stamp -Raw).Trim() } else { "" }
        $want = "$($asset.id) $($asset.updated_at)"
        if ($have -eq $want -and (Test-Path $dest) -and (Test-Path $internal)) { Note "$($exe): already the newest ($($rel.name))"; continue }
        if (Test-Path $dest) {                                          # the app open? (Windows won't let a running .exe be replaced)
            try { [IO.File]::Open($dest, 'Open', 'ReadWrite', 'None').Close() }
            catch { Note "$($exe): the app is open - close it, then run Get latest exe.bat"; continue }
        }
        Note "$($exe): downloading $($rel.name) ($([math]::Round($asset.size / 1MB)) MB)..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -UseBasicParsing -Headers @{ "User-Agent" = "InstantEasel-updater" }
        if ((Get-Item -Force $zip).Length -ne $asset.size) { throw "the download was incomplete" }
        if (Test-Path $new) { Remove-Item -Recurse -Force $new }
        [IO.Compression.ZipFile]::ExtractToDirectory($zip, $new)
        if (-not (Test-Path (Join-Path $new $exe)) -or -not (Test-Path (Join-Path $new "_internal"))) { throw "the download didn't hold the app" }
        # swap: the old one moved aside first, so it can be put back if anything goes wrong
        $oldExe = "$dest.old"; $oldInt = "$internal.old"
        foreach ($p in @($oldExe, $oldInt)) { if (Test-Path $p) { Remove-Item -Recurse -Force $p } }
        if (Test-Path $dest) { Move-Item $dest $oldExe }
        if (Test-Path $internal) { Move-Item $internal $oldInt }
        try {
            Move-Item (Join-Path $new $exe) $dest; Move-Item (Join-Path $new "_internal") $internal
        } catch {
            foreach ($p in @($dest, $internal)) { if (Test-Path $p) { Remove-Item -Recurse -Force $p } }
            if (Test-Path $oldExe) { Move-Item $oldExe $dest }
            if (Test-Path $oldInt) { Move-Item $oldInt $internal }
            throw
        }
        foreach ($p in @($oldExe, $oldInt)) { if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue } }
        Set-Content -Path $stamp -Value $want
        Note "$($exe): updated to $($rel.name)"
    } catch { Note "$($exe): couldn't update ($($_.Exception.Message)) - the one you had is unchanged" }
    finally {
        foreach ($p in @($zip, $new)) { if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue } }
    }
}
