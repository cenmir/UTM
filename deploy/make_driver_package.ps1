<#
.SYNOPSIS
    Collect the Basler USB3 Vision kernel driver into deploy\driver\ for redistribution.

.DESCRIPTION
    Run this ONCE on a machine that already has the Basler pylon Suite installed. It copies
    the five files a camera actually needs and nothing else.

    Why this exists: the pylon Suite is ~1.7 GB installed, but that is Documentation (742 MB),
    the SDK (582 MB), the Runtime (232 MB - which the pypylon wheel already bundles) and the
    pylon Viewer (119 MB). The part Windows needs in order to ENUMERATE a USB3 Vision camera
    is a ~1.9 MB kernel driver. Everything else is developer convenience.

    That makes "any student laptop can drive the rig" achievable: the app and pypylon install
    with no admin at all, and this adds one 1.9 MB, WHQL-signed driver behind a single UAC
    prompt - instead of a 2 GB download per machine.

    LICENSING - CHECK BEFORE YOU REDISTRIBUTE.
    These are Basler's files, not ours. Basler's EULA has provisions for redistributing the
    pylon runtime with a system, which is close to this situation, but confirm the terms cover
    handing the driver to students on their own laptops before hosting it anywhere. One email
    to Basler settles it. deploy\driver\ is gitignored so the binaries cannot reach the public
    repository by accident.
#>
[CmdletBinding()]
param(
    [string]$PylonRoot = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $OutDir) { $OutDir = Join-Path $DeployDir "driver" }

function Head($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Say($m)  { Write-Host "   $m" }

Head "Collecting the Basler USB3 Vision driver"

# ---------------------------------------------------------------- find pylon
if (-not $PylonRoot) {
    $roots = @("$env:ProgramFiles\Basler", "${env:ProgramFiles(x86)}\Basler") |
             Where-Object { Test-Path $_ }
    $candidates = @()
    foreach ($r in $roots) {
        $candidates += Get-ChildItem $r -Directory -ErrorAction SilentlyContinue
    }
    if (-not $candidates) {
        throw "No Basler pylon install found. Install the pylon Suite on THIS machine first, or pass -PylonRoot."
    }
    $PylonRoot = ($candidates | Sort-Object Name -Descending)[0].FullName
}
Say "pylon install: $PylonRoot"

# ---------------------------------------------------------------- locate the driver files
$need = @("plnu3v.inf", "plnu3v.sys", "plnu3v.cat", "PylonUsbRes.dll", "WdfCoInstaller01009.dll")
$src = Get-ChildItem $PylonRoot -Recurse -Filter "plnu3v.inf" -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $src) { throw "plnu3v.inf not found under $PylonRoot - is this a pylon install?" }
$srcDir = $src.DirectoryName
Say "driver folder: $srcDir"

# ---------------------------------------------------------------- copy
if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutDir | Out-Null

$total = 0
foreach ($f in $need) {
    $p = Join-Path $srcDir $f
    if (-not (Test-Path $p)) { throw "missing driver file: $f" }
    Copy-Item $p $OutDir
    $len = (Get-Item $p).Length
    $total += $len
    Say ("{0,-26} {1,8:N1} KB" -f $f, ($len / 1KB))
}

# ---------------------------------------------------------------- verify the signature
Head "Signature"
$sig = Get-AuthenticodeSignature (Join-Path $OutDir "plnu3v.cat")
Say "status : $($sig.Status)"
Say "signer : $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne "Valid") {
    Write-Host "  WARNING: catalog does not verify - Windows will refuse this driver" -ForegroundColor Yellow
}

# record which pylon version this came from
$ver = (Select-String -Path (Join-Path $OutDir "plnu3v.inf") -Pattern "^\s*DriverVer\s*=" |
        Select-Object -First 1).Line.Trim()
@"
Basler USB3 Vision kernel driver, collected from:
  $srcDir
  $ver
  collected $(Get-Date -Format 'yyyy-MM-dd') on $env:COMPUTERNAME

These are Basler's files. See deploy\make_driver_package.ps1 for the licensing note before
redistributing. Install on a target machine with deploy\install_driver.ps1 (needs admin).
"@ | Set-Content (Join-Path $OutDir "SOURCE.txt") -Encoding utf8

Head "Done"
Say ("{0} files, {1:N1} MB in {2}" -f $need.Count, ($total / 1MB), $OutDir)
Say "Install it on a target machine with:  deploy\install_driver.ps1"
Write-Host ""
