# Installing the UTM software

For students. Windows 10 or 11. Takes a few minutes.

You do **not** need Git, Python, or the 2 GB Basler pylon Suite. The installer
brings its own Python and the camera driver ships with it.

## Install

Open **PowerShell** (Start menu, type `powershell`) and paste this one line:

```powershell
irm https://raw.githubusercontent.com/cenmir/UTM/main/deploy/get.ps1 | iex
```

Press Enter and wait. It downloads the app, sets up Python, and puts a
**UTM Control** icon on your Desktop.

Partway through, Windows asks for administrator with a UAC prompt. That is the
camera driver — 1.8 MB, signed by Microsoft. It is the only step that needs
admin, and the whole install is the only time you need it.

- **Your laptop will get the camera plugged into it?** Click Yes.
- **Not sure?** Click Yes anyway. It is harmless on a machine with no camera.
- **Definitely no camera?** You can click No. Everything else still works.

## Run it

Double-click the **UTM Control** icon on your Desktop.

The app runs on any laptop, with or without the rig. Without hardware you can
still open a CSV, plot it, crop it, and measure strain from a recorded video in
the **DIC Post-Processing** tab. You just cannot start a test.

## Update

Run the same one-line command again. Your `.venv`, your recipes, and your test
data are kept — the installer only replaces the program itself.

## If something goes wrong

**"running scripts is disabled on this system"** — PowerShell is locked down.
Run this once, then retry the install:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**The camera is not found.** You probably declined the UAC prompt. Install the
driver on its own:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\UTM\deploy\install_driver.ps1"
```

Then unplug the camera and plug it back in. Use a **USB 3** port — the blue one.

**Still not found.** Open Device Manager and look for an unknown USB device. If
the camera appears there, the driver did not take; re-run the line above.

**No COM port for the rig.** Check the USB cable, then press **Scan for COM
ports** in the app. The rig shows up as `USB2.0-Serial`.

## Installing somewhere else

```powershell
$env:UTM_DEST = "D:\UTM"     # default is C:\Users\<you>\UTM
$env:UTM_NO_DRIVER = "1"     # skip the camera driver entirely
irm https://raw.githubusercontent.com/cenmir/UTM/main/deploy/get.ps1 | iex
```
