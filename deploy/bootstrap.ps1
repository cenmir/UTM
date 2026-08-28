<#
    UTM one-line installer.

        irm https://raw.githubusercontent.com/cenmir/UTM/main/deploy/bootstrap.ps1 | iex

    Clones (or updates) the repo and runs deploy\install.ps1, which builds a venv,
    installs dependencies and puts a double-clickable icon on the Desktop.

    Defaults to the ANALYSIS profile - no pypylon, no Basler runtime needed. That is what
    a student laptop wants. For the lab PC that drives the machine:

        $env:UTM_PROFILE='rig'; irm <url> | iex

    A shallow clone is used because the repo carries the slide decks and figures.
#>
$ErrorActionPreference = "Stop"

$RepoUrl  = "https://github.com/cenmir/UTM.git"
$Dest     = if ($env:UTM_DEST) { $env:UTM_DEST } else { Join-Path $HOME "UTM" }
$Profile  = if ($env:UTM_PROFILE) { $env:UTM_PROFILE } else { "analysis" }

function Head($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Say($m)  { Write-Host "   $m" }

Head "UTM bootstrap"
Say "target : $Dest"
Say "profile: $Profile"

# ---------------------------------------------------------------- prerequisites
Head "Checking prerequisites"
$missing = @()
if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) { $missing += "git" }
$hasPy = ($null -ne (Get-Command py -ErrorAction SilentlyContinue)) -or
         ($null -ne (Get-Command python -ErrorAction SilentlyContinue))
if (-not $hasPy) { $missing += "python" }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host ""
    if ($missing -contains "git")    { Write-Host "  git   : https://git-scm.com/download/win" }
    if ($missing -contains "python") { Write-Host "  python: https://www.python.org/downloads/  (tick 'Add python.exe to PATH')" }
    Write-Host ""
    throw "Install the above, open a NEW terminal, and re-run."
}
Say "git and python found"

# ---------------------------------------------------------------- clone / update
if (Test-Path (Join-Path $Dest ".git")) {
    Head "Updating existing checkout"
    Push-Location $Dest
    git pull --ff-only
    if (-not $?) { Pop-Location; throw "git pull failed - resolve it by hand at $Dest" }
    Pop-Location
} else {
    Head "Cloning"
    if (Test-Path $Dest) { throw "$Dest exists but is not a git checkout. Move it or set `$env:UTM_DEST." }
    git clone --depth 1 $RepoUrl $Dest
    if (-not $?) { throw "git clone failed" }
}
Say "repo ready at $Dest"

# ---------------------------------------------------------------- install
$Installer = Join-Path $Dest "deploy\install.ps1"
if (-not (Test-Path $Installer)) { throw "installer not found at $Installer" }

Head "Running installer"
if ($Profile -eq "rig") {
    & powershell -ExecutionPolicy Bypass -File $Installer -Rig
} else {
    & powershell -ExecutionPolicy Bypass -File $Installer
}
if (-not $?) { throw "installer failed" }

Head "Bootstrap complete"
Say "Look for the UTM icon on your Desktop."
Write-Host ""
