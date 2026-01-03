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

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()
MAIN_PY = SCRIPT_DIR / "main.py"
UI_FILE = SCRIPT_DIR / "ui" / "utm_mainwindow.ui"

# Read version from main.py
def get_version():
    with open(MAIN_PY, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return "0.0.0"

VERSION = get_version()
APP_NAME = f"UTM_Control_v{VERSION}"

def main():
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
        # Clean build
        "--clean",
        # Main script
        str(MAIN_PY),
    ]

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
