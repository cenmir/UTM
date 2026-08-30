<#
.SYNOPSIS
    Install the Basler USB3 Vision kernel driver so this PC can see the camera.

.DESCRIPTION
    Run this ONCE per machine that will have the camera plugged into it. It needs
    administrator - every kernel driver install does - and re-elevates itself, so one UAC
    prompt is the whole cost.

    This is the ONLY step in the whole setup that needs admin. The app and pypylon install
    with no elevation at all.

    What it does NOT need: the 2 GB pylon Suite. The pypylon wheel already carries the pylon
    runtime; the only missing piece on a fresh machine is the ~1.9 MB kernel driver that lets
    Windows enumerate a USB3 Vision device. Without it the camera appears as an unknown device
    (or not at all) no matter what pip has installed.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File deploy\install_driver.ps1
#>
[CmdletBinding()]
param(
    [string]$DriverDir = "",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $DriverDir) { $DriverDir = Join-Path $DeployDir "driver" }

function Head($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Say($m)  { Write-Host "   $m" }

# ---------------------------------------------------------------- elevate
$isAdmin = ([Security.Principal.WindowsPrincipal] `
            [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Installing a kernel driver needs administrator - asking for it now..." -ForegroundColor Yellow
    $argl = @("-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`"")
    if ($DriverDir) { $argl += @("-DriverDir","`"$DriverDir`"") }
    if ($Uninstall) { $argl += "-Uninstall" }
    try {
        $p = Start-Process powershell -Verb RunAs -ArgumentList $argl -Wait -PassThru
    } catch {
        # Declining the UAC prompt throws here. That is a choice, not a crash: say so and
        # hand back a distinct code so an unattended caller can tell it apart from a failure.
        Write-Host "Administrator was declined - the driver was NOT installed." -ForegroundColor Yellow
        exit 2
    }
    # Without this the caller cannot tell whether the elevated half worked.
    exit $p.ExitCode
}

Head "Basler USB3 Vision driver"

$inf = Join-Path $DriverDir "plnu3v.inf"
if (-not (Test-Path $inf)) {
    Write-Host ""
    Write-Host "  Driver files not found at: $DriverDir" -ForegroundColor Red
    Write-Host ""
    Write-Host "  They are not in the repository - they are Basler's, and redistributing them"
    Write-Host "  is a licensing question. Produce them once from a machine that has the pylon"
    Write-Host "  Suite installed:"
    Write-Host ""
    Write-Host "      powershell -ExecutionPolicy Bypass -File deploy\make_driver_package.ps1"
    Write-Host ""
    Write-Host "  Or install the full pylon Suite on this machine instead:"
    Write-Host "      https://www.baslerweb.com/en/downloads/software-downloads/"
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    Head "Removing"
    $existing = pnputil /enum-drivers | Select-String -Pattern "plnu3v.inf" -Context 2,0
    if (-not $existing) { Say "not installed"; return }
    $published = (pnputil /enum-drivers |
                  Select-String -Pattern "Published Name" -Context 0,4 |
                  Where-Object { $_.Context.PostContext -match "plnu3v.inf" } |
                  ForEach-Object { ($_.Line -split ":")[1].Trim() })
    foreach ($p in $published) {
        Say "removing $p"
        pnputil /delete-driver $p /uninstall /force
    }
    return
}

# ---------------------------------------------------------------- already there?
# get.ps1 runs this on every install, and re-running the one-liner to update the app must
# not mean a second driver install. Staged already is success, not work to redo.
if (pnputil /enum-drivers | Select-String -Pattern "plnu3v.inf" -Quiet) {
    Head "Basler USB3 Vision driver"
    Say "already staged in the driver store - nothing to do"
    Write-Host ""
    exit 0
}

# ---------------------------------------------------------------- verify then install
Head "Verifying the signature"
$sig = Get-AuthenticodeSignature (Join-Path $DriverDir "plnu3v.cat")
Say "status : $($sig.Status)"
Say "signer : $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne "Valid") {
    throw "The driver catalog does not verify. Windows will refuse it. Do not force this - re-collect the files from a genuine pylon install."
}

Head "Installing"
Say "pnputil /add-driver `"$inf`" /install"
pnputil /add-driver "$inf" /install
if ($LASTEXITCODE -ne 0) { throw "pnputil failed with exit code $LASTEXITCODE" }

Head "Result"
$staged = pnputil /enum-drivers | Select-String -Pattern "plnu3v" -Context 3,3
if ($staged) {
    Say "driver is staged in the driver store"
} else {
    Say "WARNING: could not confirm the driver is staged"
}

Write-Host ""
Say "Done. Plug the camera in (or replug it) and start the app."
Say "If it still does not appear, check Device Manager for an 'Unknown USB Device'."
Write-Host ""
