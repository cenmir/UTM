<#
.SYNOPSIS
    Set up the UTM app and put a double-clickable icon on the Desktop and Start Menu.

.DESCRIPTION
    Creates a virtual environment, installs dependencies, and creates shortcuts that
    launch the app with pythonw.exe (no console window).

    Two profiles:
      -Rig       full install including pypylon. For the lab PC that drives the machine.
      -Analysis  no pypylon. For a student laptop: post-processing, CSV load, reports.
                 This is the default, because it is what most machines need and it is
                 the only one that works without the Basler Pylon runtime installed.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\install.ps1
    powershell -ExecutionPolicy Bypass -File deploy\install.ps1 -Rig
    powershell -ExecutionPolicy Bypass -File deploy\install.ps1 -Rig -NoShortcut
#>
[CmdletBinding()]
param(
    [switch]$Rig,
    [switch]$Analysis,
    [switch]$NoShortcut,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Split-Path -Parent $DeployDir
$AppDir    = Join-Path $RepoRoot "Software\UTM_PyQt6"
$MainPy    = Join-Path $AppDir "main.py"
$VenvDir   = Join-Path $RepoRoot ".venv"
$IconPath  = Join-Path $DeployDir "utm.ico"
$ReqFile   = Join-Path $RepoRoot "requirements.txt"

if ($Rig -and $Analysis) { throw "Pick one of -Rig or -Analysis, not both." }
$Profile = "Analysis"
if ($Rig) { $Profile = "Rig" }

function Say($msg)  { Write-Host "  $msg" }
function Head($msg) { Write-Host ""; Write-Host "== $msg" -ForegroundColor Cyan }

Head "UTM install - $Profile profile"
Say "repo   : $RepoRoot"
Say "app    : $AppDir"

if (-not (Test-Path $MainPy)) { throw "main.py not found at $MainPy - is this the right repo?" }

# ---------------------------------------------------------------- find python
Head "Locating Python"
if ($Python -eq "") {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        $Python = "py"
    } else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($null -ne $cmd) { $Python = "python" }
    }
}
if ($Python -eq "") {
    throw "No Python found. Install Python 3.11+ from python.org (tick 'Add to PATH'), then re-run."
}
$ver = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Say "using '$Python' (Python $ver)"

# ---------------------------------------------------------------- venv
Head "Virtual environment"
$VenvPyw = Join-Path $VenvDir "Scripts\pythonw.exe"
$VenvPy  = Join-Path $VenvDir "Scripts\python.exe"
if (Test-Path $VenvPy) {
    Say "reusing existing venv at $VenvDir"
} else {
    Say "creating $VenvDir"
    & $Python -m venv $VenvDir
    if (-not $?) { throw "venv creation failed" }
}

# ---------------------------------------------------------------- dependencies
Head "Dependencies"
& $VenvPy -m pip install --upgrade pip --quiet
if (-not (Test-Path $ReqFile)) { throw "requirements.txt not found at $ReqFile" }

if ($Profile -eq "Rig") {
    Say "installing everything in requirements.txt (includes pypylon)"
    & $VenvPy -m pip install -r $ReqFile
} else {
    # Strip pypylon: it needs the Basler Pylon runtime, which a student laptop will not have.
    # Every offline path still runs - utm_analysis and friends are deliberately stdlib-only.
    Say "installing without pypylon (analysis profile)"
    $tmp = Join-Path $env:TEMP "utm_req_analysis.txt"
    Get-Content $ReqFile | Where-Object { $_ -notmatch '^\s*pypylon' } | Set-Content -Encoding utf8 $tmp
    & $VenvPy -m pip install -r $tmp
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
if (-not $?) { throw "dependency install failed" }

# ---------------------------------------------------------------- smoke test
Head "Smoke test"
$env:QT_QPA_PLATFORM = "offscreen"
& $VenvPy -c "import PyQt6, matplotlib, numpy, serial; print('imports OK')"
if (-not $?) { throw "smoke test failed - the app will not start" }
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- shortcuts
if ($NoShortcut) {
    Head "Shortcuts skipped (-NoShortcut)"
} else {
    Head "Shortcuts"
    if (-not (Test-Path $IconPath)) {
        Say "icon missing - generating it"
        & $VenvPy (Join-Path $DeployDir "make_icon.py")
    }

    $name = "UTM Control"
    if ($Profile -eq "Analysis") { $name = "UTM Analysis" }

    $targets = @(
        [System.Environment]::GetFolderPath("Desktop"),
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs")
    )

    $shell = New-Object -ComObject WScript.Shell
    foreach ($dir in $targets) {
        if (-not (Test-Path $dir)) { continue }
        $lnk = Join-Path $dir "$name.lnk"
        $sc = $shell.CreateShortcut($lnk)
        $sc.TargetPath       = $VenvPyw          # pythonw = no console window
        $sc.Arguments        = '"' + $MainPy + '"'
        $sc.WorkingDirectory = $AppDir           # tools and relative paths expect this
        $sc.IconLocation     = $IconPath
        $sc.Description      = "Universal Testing Machine control and analysis"
        $sc.Save()
        Say "created $lnk"
    }
}

Head "Done"
Say "Launch from the Desktop icon, or run:"
Say "  `"$VenvPyw`" `"$MainPy`""
Write-Host ""
