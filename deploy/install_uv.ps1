<#
.SYNOPSIS
    Set up the UTM app on a fresh PC using uv. No admin rights, no separate Python install.

.DESCRIPTION
    uv installs its own Python, so a fresh student machine needs nothing preinstalled
    except uv itself.

    ONE profile: every machine gets the same app, hardware or not. pypylon installs anywhere
    and simply finds no camera when there is none, so the app starts and behaves identically.
    Nothing here needs administrator.

    The camera also needs the Basler USB3 Vision kernel driver, which is not a Python
    package. deploy/driver/ carries it - 1.8 MB, WHQL-signed - and this script installs it
    for you, so the whole setup is one command and one UAC prompt. Not the 2 GB pylon Suite.

    -NoDriver skips that step, as does declining the UAC prompt; either way the app still
    installs and runs. It just will not see a camera.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\install_uv.ps1
#>
[CmdletBinding()]
param(
    [switch]$NoShortcut,
    [switch]$NoDriver,
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"
$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Split-Path -Parent $DeployDir
$AppDir    = Join-Path $RepoRoot "Software\UTM_PyQt6"
$MainPy    = Join-Path $AppDir "main.py"
$IconPath  = Join-Path $DeployDir "utm.ico"

function Head($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Say($m)  { Write-Host "   $m" }

Head "UTM install via uv"
Say "repo: $RepoRoot"
if (-not (Test-Path $MainPy)) { throw "main.py not found at $MainPy" }

# ---------------------------------------------------------------- uv
Head "Checking uv"
if ($null -eq (Get-Command uv -ErrorAction SilentlyContinue)) {
    Say "uv not found - installing it (per-user, no admin)"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if ($null -eq (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installed but not on PATH. Open a NEW terminal and re-run."
    }
}
Say "uv $(uv --version)"

# ---------------------------------------------------------------- python + deps
Head "Python $PythonVersion"
Push-Location $RepoRoot
try {
    uv python install $PythonVersion
    if (-not $?) { throw "uv could not install Python $PythonVersion" }

    Head "Dependencies"
    Say "one set for every machine - pypylon included, harmless without a camera"
    uv sync --python $PythonVersion
    if (-not $?) { throw "dependency install failed" }

    Head "Smoke test"
    $env:QT_QPA_PLATFORM = "offscreen"
    uv run python -c "import PyQt6, numpy, matplotlib, cv2, serial; print('imports OK')"
    if (-not $?) { throw "smoke test failed - the app will not start" }
    Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
} finally {
    Pop-Location
}

$VenvPyw = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$VenvPy  = Join-Path $RepoRoot ".venv\Scripts\python.exe"

# ---------------------------------------------------------------- shortcut
if ($NoShortcut) {
    Head "Shortcut skipped"
} elseif (Test-Path $VenvPyw) {
    Head "Shortcut"
    if (-not (Test-Path $IconPath)) { & $VenvPy (Join-Path $DeployDir "make_icon.py") }
    $name = "UTM Control"
    $shell = New-Object -ComObject WScript.Shell
    foreach ($dir in @([System.Environment]::GetFolderPath("Desktop"),
                       (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))) {
        if (-not (Test-Path $dir)) { continue }
        $lnk = Join-Path $dir "$name.lnk"
        $sc = $shell.CreateShortcut($lnk)
        $sc.TargetPath       = $VenvPyw         # pythonw = no console window
        $sc.Arguments        = '"' + $MainPy + '"'
        $sc.WorkingDirectory = $AppDir
        $sc.IconLocation     = $IconPath
        $sc.Description      = "Universal Testing Machine control and DIC strain"
        $sc.Save()
        Say "created $lnk"
    }
}

# ---------------------------------------------------------------- camera driver
# The one remaining manual step used to live here as a printed instruction, and printed
# instructions get skipped. Install it, and let declining be the deliberate act instead.
$DriverScript = Join-Path $DeployDir "install_driver.ps1"
$DriverInf    = Join-Path $DeployDir "driver\plnu3v.inf"
$driverState  = "skipped"

if ($NoDriver) {
    $driverState = "skipped by request"
} elseif (-not (Test-Path $DriverInf)) {
    $driverState = "no payload"
} elseif (pnputil /enum-drivers | Select-String -Pattern "plnu3v.inf" -Quiet) {
    $driverState = "already installed"
} else {
    Head "Camera driver"
    Say "The camera needs a kernel driver - 1.8 MB, WHQL-signed, shipped with this install."
    Say "This is the ONLY step that needs administrator. Approve the UAC prompt, or decline"
    Say "it if this machine will never have the camera plugged in."
    & powershell -ExecutionPolicy Bypass -File $DriverScript
    $rc = $LASTEXITCODE
    # Never fail the whole install over this: a laptop with no camera is a valid outcome.
    if     ($rc -eq 0) { $driverState = "installed" }
    elseif ($rc -eq 2) { $driverState = "declined" }
    else               { $driverState = "failed (exit $rc)" }
}

Head "Done"
Write-Host ""
switch -Wildcard ($driverState) {
    "installed"         { Write-Host "  Camera driver: installed. Plug the camera in and start the app." -ForegroundColor Green }
    "already installed" { Write-Host "  Camera driver: already present - left alone." -ForegroundColor Green }
    "skipped by request" { Write-Host "  Camera driver: skipped (-NoDriver). The app runs; the camera will not be seen." }
    "no payload"        {
        Write-Host "  Camera driver: NOT installed - the driver files are missing from this copy." -ForegroundColor Yellow
        Write-Host "  If this machine gets the camera, install the full pylon Suite instead:"
        Write-Host "     https://www.baslerweb.com/en/downloads/software-downloads/"
    }
    default             {
        Write-Host "  Camera driver: $driverState." -ForegroundColor Yellow
        Write-Host "  The app is installed and runs fine. If you later plug the camera into this"
        Write-Host "  machine, run this once:"
        Write-Host "     powershell -ExecutionPolicy Bypass -File `"$DriverScript`""
    }
}

Say "Launch from the icon, or:  uv run python `"$MainPy`""
Write-Host ""

# pnputil and the nested powershell calls above leave $LASTEXITCODE set; be explicit so
# get.ps1's success check reflects the app install, not the last native command to run.
exit 0
