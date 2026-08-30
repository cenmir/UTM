<#
    UTM one-line installer. No git, no Python, no admin.

        irm https://raw.githubusercontent.com/cenmir/UTM/main/deploy/get.ps1 | iex

    Downloads the app, installs uv and a private Python, and puts an icon on the Desktop.
    Windows already has everything this needs: Invoke-WebRequest and Expand-Archive are
    built in, so nothing has to be installed before running it.

    One profile: every machine gets the same app. A laptop with no camera and no rig
    runs it fine - it just cannot start a test. The rig PC additionally needs the
    Basler Pylon Suite, installed once as administrator.

    Knobs:  $env:UTM_DEST (default $HOME\UTM), $env:UTM_REF (default main)
#>
$ErrorActionPreference = "Stop"

$Owner = "cenmir"
$Repo  = "UTM"
$Ref     = if ($env:UTM_REF)     { $env:UTM_REF }     else { "main" }
$Dest    = if ($env:UTM_DEST)    { $env:UTM_DEST }    else { Join-Path $HOME "UTM" }

function Head($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Say($m)  { Write-Host "   $m" }

Head "UTM installer"
Say "target : $Dest"

# TLS 1.2 for older Windows PowerShell hosts
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$tmp = Join-Path $env:TEMP ("utm_get_" + [Guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $tmp | Out-Null
$zip = Join-Path $tmp "utm.zip"

# ---------------------------------------------------------------- fetch
Head "Downloading"
$got = $false

# Prefer a trimmed release asset: the app is ~1.4 MB, the whole repo is ~21 MB of which
# documentation and CAD are most. Forty students should not each pull the slide decks.
try {
    $rel = Invoke-RestMethod "https://api.github.com/repos/$Owner/$Repo/releases/latest" `
        -Headers @{ "User-Agent" = "utm-installer" }
    $asset = $rel.assets | Where-Object { $_.name -like "UTM-app*.zip" } | Select-Object -First 1
    if ($asset) {
        Say "release asset: $($asset.name)  ($([math]::Round($asset.size/1MB,1)) MB)"
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
        $got = $true
    }
} catch {
    Say "no release asset available"
}

if (-not $got) {
    Say "falling back to the $Ref branch archive (larger - includes docs and CAD)"
    Invoke-WebRequest "https://codeload.github.com/$Owner/$Repo/zip/refs/heads/$Ref" `
        -OutFile $zip -UseBasicParsing
}
Say "downloaded $([math]::Round((Get-Item $zip).Length/1MB,1)) MB"

# ---------------------------------------------------------------- extract
Head "Extracting"
$unpack = Join-Path $tmp "unpack"
Expand-Archive -Path $zip -DestinationPath $unpack -Force

# a branch archive nests everything under <repo>-<ref>/; a release asset may not
$root = $unpack
$inner = Get-ChildItem $unpack -Directory
if ($inner.Count -eq 1 -and -not (Test-Path (Join-Path $unpack "pyproject.toml"))) {
    $root = $inner[0].FullName
}
if (-not (Test-Path (Join-Path $root "Software\UTM_PyQt6\main.py"))) {
    throw "archive does not look like the UTM app (no Software\UTM_PyQt6\main.py under $root)"
}

if (Test-Path $Dest) {
    if (Test-Path (Join-Path $Dest ".git")) {
        throw "$Dest is a git checkout - update it with git pull instead, or set `$env:UTM_DEST."
    }
    Say "replacing the previous copy at $Dest"
    # keep whatever the operator has made: their venv, their recipes, their test data
    foreach ($keep in @(".venv", "Software\UTM_PyQt6\recipes", "Software\UTM_PyQt6\Test data")) {
        $src = Join-Path $Dest $keep
        if (Test-Path $src) { Move-Item $src (Join-Path $tmp (Split-Path $keep -Leaf)) -Force }
    }
    Remove-Item $Dest -Recurse -Force
}
New-Item -ItemType Directory -Path $Dest -Force | Out-Null
Copy-Item (Join-Path $root "*") $Dest -Recurse -Force
foreach ($keep in @(".venv", "recipes", "Test data")) {
    $saved = Join-Path $tmp $keep
    if (-not (Test-Path $saved)) { continue }
    $back = if ($keep -eq ".venv") { Join-Path $Dest ".venv" }
            else { Join-Path $Dest "Software\UTM_PyQt6\$keep" }
    if (Test-Path $back) { Remove-Item $back -Recurse -Force }
    Move-Item $saved $back -Force
    Say "kept your $keep"
}
Say "installed to $Dest"

# ---------------------------------------------------------------- install
$installer = Join-Path $Dest "deploy\install_uv.ps1"
if (-not (Test-Path $installer)) { throw "installer missing at $installer" }

Head "Setting up Python and dependencies"
& powershell -ExecutionPolicy Bypass -File $installer
if (-not $?) { throw "setup failed" }

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Head "Done"
Say "Look for the UTM icon on your Desktop."
Write-Host ""
