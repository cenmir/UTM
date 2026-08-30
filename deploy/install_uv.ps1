<#
.SYNOPSIS
    Set up the UTM app on a fresh PC using uv. No admin rights, no separate Python install.

.DESCRIPTION
    uv installs its own Python, so a fresh student machine needs nothing preinstalled
    except uv itself.

    ONE profile: every machine gets the same app, hardware or not. pypylon installs anywhere
    and simply finds no camera when there is none, so the app starts and behaves identically.
    Nothing here needs administrator.

    The RIG PC additionally needs the Basler Pylon Suite for its USB3 Vision kernel driver -
    a separate ~2 GB install, once, as administrator. That is not a Python package.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\install_uv.ps1
#>
[CmdletBinding()]
param(
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

Head "Done"
Write-Host ""
Write-Host "  ON THE RIG PC ONLY, one more step:" -ForegroundColor Yellow
Write-Host "  pypylon is installed, but the camera also needs the Basler Pylon Camera Software"
Write-Host "  Suite for its USB3 Vision KERNEL DRIVER. Without it Windows will not enumerate"
Write-Host "  the camera at all, whatever pip installed. Once, as administrator:"
Write-Host "     https://www.baslerweb.com/en/downloads/software-downloads/"
Write-Host "  On a laptop with no camera, ignore this - the app runs fine without it."

Say "Launch from the icon, or:  uv run python `"$MainPy`""
Write-Host ""
