#!/usr/bin/env python3
"""
Build script for creating UTM Control executable using PyInstaller.

Usage:
    python build_exe.py

This will create a standalone executable in the 'dist' folder.
"""

import subprocess
import sys
import os
from pathlib import Path

# This script lives in tools/, so the app root is one level UP. It used to assume it
# sat beside main.py; after the 2026-08-25 reorganisation that made every path here
# point at tools/main.py, which does not exist, and get_version() died on import.
SCRIPT_DIR = Path(__file__).parent.parent.absolute()   # Software/UTM_PyQt6
DEPLOY_DIR = SCRIPT_DIR.parent.parent / "deploy"       # repo-root/deploy
MAIN_PY = SCRIPT_DIR / "main.py"
UI_FILE = SCRIPT_DIR / "ui" / "utm_mainwindow.ui"
HELP_DIR = SCRIPT_DIR / "ui" / "help"
ICON = DEPLOY_DIR / "utm.ico"

# Read version from main.py
def get_version():
    with open(MAIN_PY, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return "0.0.0"

VERSION = get_version()
APP_NAME = f"UTM_Control_v{VERSION}"
if "--analysis" in sys.argv:
    APP_NAME = f"UTM_Analysis_v{VERSION}"

ANALYSIS_ONLY = "--analysis" in sys.argv


def main():
    if ANALYSIS_ONLY:
        print("Profile: ANALYSIS (no pypylon) - for student laptops")
    else:
        print("Profile: RIG (with pypylon) - pass --analysis for the student build")
    print(f"Building {APP_NAME}...")
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"Main file: {MAIN_PY}")
    print(f"UI file: {UI_FILE}")

    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",           # Single executable
        "--windowed",          # No console window
        "--noconfirm",         # Overwrite without asking
        # Include the UI file
        "--add-data", f"{UI_FILE};ui",
        # ...and the mode-help diagrams, or every "?" button shows a blank image.
        # These fail SILENTLY when missing - see Software/UTM_PyQt6/README.md.
        "--add-data", f"{HELP_DIR};ui/help",
        # Clean build
        "--clean",
        # Main script
        str(MAIN_PY),
    ]

    if ICON.exists():
        cmd[-2:-2] = ["--icon", str(ICON)]
    else:
        print(f"[warn] no icon at {ICON} - run: python deploy/make_icon.py")

    if not ANALYSIS_ONLY:
        pass
    else:
        # Student laptops have no Basler Pylon runtime. Excluding pypylon keeps the
        # offline path (post-processing, CSV load, reports) working everywhere.
        cmd[-1:-1] = ["--exclude-module", "pypylon"]

    print("\nRunning PyInstaller...")
    print(" ".join(cmd))
    print()

    # Change to script directory and run
    os.chdir(SCRIPT_DIR)
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = SCRIPT_DIR / "dist" / f"{APP_NAME}.exe"
        print(f"\n[OK] Build successful!")
        print(f"  Executable: {exe_path}")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"\n[FAIL] Build failed with return code {result.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
