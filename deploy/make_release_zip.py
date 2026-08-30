#!/usr/bin/env python3
"""Build the trimmed archive that deploy/get.ps1 downloads.

The repository is ~21 MB tracked, of which documentation and CAD are most of it. The app
itself is ~1.4 MB. Forty students installing the analysis build should not each pull the
slide decks, the poster figures and the CAD.

    python deploy/make_release_zip.py
    gh release create v0.5.4 deploy/dist/UTM-app-0.5.4.zip --title "UTM 0.5.4" --notes "..."

get.ps1 looks for an asset named UTM-app*.zip on the latest release and falls back to the
branch archive if there is none, so publishing this is an optimisation, not a requirement.
"""
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# What a working install needs, and nothing else.
INCLUDE_DIRS = [
    "Software/UTM_PyQt6",
    "deploy",
]
INCLUDE_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "INSTALL.md",     # the student-facing setup notes, incl. what the UAC prompt is for
    "LICENSE",
]

# Inside those directories, keep the app and leave the evidence behind.
SKIP_DIR_NAMES = {
    "__pycache__", ".git", ".venv", "output", "dist", "build",
    "Test data",          # 54 GB of measurements live here
    "recipes",            # seeded on first launch; the operator's own profiles are not ours
    "reports",
}
SKIP_SUFFIXES = (".pyc", ".pyo", ".csv", ".avi", ".mkv", ".tif", ".tiff", ".mat", ".h5")


def version():
    main_py = os.path.join(ROOT, "Software", "UTM_PyQt6", "main.py")
    with open(main_py, encoding="utf-8") as f:
        for line in f:
            m = re.match(r'__version__\s*=\s*["\']([^"\']+)', line)
            if m:
                return m.group(1)
    return "0.0.0"


def wanted(path):
    parts = set(path.replace("\\", "/").split("/"))
    if parts & SKIP_DIR_NAMES:
        return False
    return not path.lower().endswith(SKIP_SUFFIXES)


def main():
    ver = version()
    out_dir = os.path.join(HERE, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"UTM-app-{ver}.zip")

    n, total = 0, 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel_dir in INCLUDE_DIRS:
            base = os.path.join(ROOT, rel_dir)
            if not os.path.isdir(base):
                sys.exit(f"missing directory: {rel_dir}")
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, ROOT).replace("\\", "/")
                    if not wanted(rel):
                        continue
                    z.write(full, rel)
                    n += 1
                    total += os.path.getsize(full)
        for rel in INCLUDE_FILES:
            full = os.path.join(ROOT, rel)
            if os.path.isfile(full):
                z.write(full, rel)
                n += 1
                total += os.path.getsize(full)

    size = os.path.getsize(out)
    print(f"wrote {out}")
    print(f"  {n} files, {total/1e6:.1f} MB raw -> {size/1e6:.1f} MB zipped")
    print()
    print("publish it with:")
    print(f'  gh release create v{ver} "{out}" --title "UTM {ver}" --notes "..."')


if __name__ == "__main__":
    main()
