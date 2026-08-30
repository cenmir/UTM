<#
.SYNOPSIS
    Set up the UTM app on a fresh PC using uv. No admin rights, no separate Python install.

.DESCRIPTION
    uv installs its own Python, so a fresh student machine needs nothing preinstalled except
    uv itself. Two profiles:

      (default)  ANALYSIS - open a CSV, plot, crop, compute properties, DIC post-processing
                 from recorded video. No camera, no drivers, no admin.
      -Rig       adds pypylon for the live Basler camera. ONLY for the PC wired to the rig,
                 and it additionally needs the Basler Pylon Suite installed separately.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\install_uv.ps1
    powershell -ExecutionPolicy Bypass -File deploy\install_uv.ps1 -Rig
#>
[CmdletBinding()]
param(
    [switch]$Rig,
    [switch]$NoShortcut,
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

$profileName = if ($Rig) { "RIG (with camera)" } else { "ANALYSIS (no camera)" }
Head "UTM install via uv - $profileName"
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
    if ($Rig) {
        Say "profile: rig (includes pypylon)"
        uv sync --extra rig --python $PythonVersion
    } else {
        Say "profile: analysis (no pypylon, no drivers needed)"
        uv sync --python $PythonVersion
    }
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
    $name = if ($Rig) { "UTM Control" } else { "UTM Analysis" }
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
        $sc.Description      = "Universal Testing Machine - $profileName"
        $sc.Save()
        Say "created $lnk"
    }
}

Head "Done"
if ($Rig) {
    Write-Host ""
    Write-Host "  ONE MORE STEP for the rig PC:" -ForegroundColor Yellow
    Write-Host "  pypylon is installed, but the camera also needs the Basler Pylon Camera"
    Write-Host "  Software Suite for its USB3 Vision KERNEL DRIVER. Without it Windows will"
    Write-Host "  not enumerate the camera at all. Install it once, as administrator:"
    Write-Host "     https://www.baslerweb.com/en/downloads/software-downloads/"
}
Say "Launch from the icon, or:  uv run python `"$MainPy`""
Write-Host ""
