#!/usr/bin/env bash
# Set up the UTM app on macOS or Linux and create a double-clickable launcher.
#
#   ./deploy/install.sh              analysis profile (no pypylon) - default
#   ./deploy/install.sh --rig        full install including pypylon
#   ./deploy/install.sh --no-shortcut
#
# Not the priority platform - the rig is Windows. This exists so the offline
# analysis path (post-processing, CSV load, reports) works on a student's Mac or
# Linux laptop, which is the only place it is actually needed.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$DEPLOY_DIR")"
APP_DIR="$REPO_ROOT/Software/UTM_PyQt6"
MAIN_PY="$APP_DIR/main.py"
VENV_DIR="$REPO_ROOT/.venv"
REQ_FILE="$REPO_ROOT/requirements.txt"
ICON_PNG="$DEPLOY_DIR/utm.png"

PROFILE="analysis"
MAKE_SHORTCUT=1
for arg in "$@"; do
  case "$arg" in
    --rig)          PROFILE="rig" ;;
    --analysis)     PROFILE="analysis" ;;
    --no-shortcut)  MAKE_SHORTCUT=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

head() { printf '\n== %s\n' "$1"; }
say()  { printf '   %s\n' "$1"; }

head "UTM install - $PROFILE profile"
say "repo: $REPO_ROOT"
[ -f "$MAIN_PY" ] || { echo "main.py not found at $MAIN_PY" >&2; exit 1; }

head "Locating Python"
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "No Python 3 found. Install Python 3.11+ and re-run." >&2; exit 1; }
say "using $PY ($("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])'))"

head "Virtual environment"
if [ -x "$VENV_DIR/bin/python" ]; then
  say "reusing $VENV_DIR"
else
  say "creating $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
fi
VPY="$VENV_DIR/bin/python"

head "Dependencies"
"$VPY" -m pip install --upgrade pip --quiet
if [ "$PROFILE" = "rig" ]; then
  say "installing everything (includes pypylon)"
  "$VPY" -m pip install -r "$REQ_FILE"
else
  # pypylon needs the Basler runtime; skip it. Offline analysis is stdlib-only anyway.
  say "installing without pypylon"
  TMP_REQ="$(mktemp)"
  grep -v '^[[:space:]]*pypylon' "$REQ_FILE" > "$TMP_REQ"
  "$VPY" -m pip install -r "$TMP_REQ"
  rm -f "$TMP_REQ"
fi

head "Smoke test"
QT_QPA_PLATFORM=offscreen "$VPY" -c "import PyQt6, matplotlib, numpy, serial; print('imports OK')"

if [ "$MAKE_SHORTCUT" -eq 0 ]; then
  head "Shortcut skipped"
else
  [ -f "$ICON_PNG" ] || "$VPY" "$DEPLOY_DIR/make_icon.py"
  case "$(uname -s)" in
    Darwin)
      head "macOS launcher"
      # A .command file is double-clickable in Finder. A real .app bundle would be
      # nicer but needs py2app or codesigning; this is the honest cheap version.
      CMD="$HOME/Desktop/UTM Control.command"
      cat > "$CMD" <<EOF
#!/usr/bin/env bash
cd "$APP_DIR"
exec "$VPY" "$MAIN_PY"
EOF
      chmod +x "$CMD"
      say "created $CMD"
      say "note: Finder may need right-click > Open the first time (Gatekeeper)"
      ;;
    Linux)
      head "Linux launcher"
      DESKTOP_DIR="$HOME/.local/share/applications"
      mkdir -p "$DESKTOP_DIR"
      DFILE="$DESKTOP_DIR/utm-control.desktop"
      cat > "$DFILE" <<EOF
[Desktop Entry]
Type=Application
Name=UTM Control
Comment=Universal Testing Machine control and analysis
Exec="$VPY" "$MAIN_PY"
Path=$APP_DIR
Icon=$ICON_PNG
Terminal=false
Categories=Science;Engineering;
EOF
      chmod +x "$DFILE"
      if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" || true
      fi
      say "created $DFILE"
      ;;
    *)
      say "unknown platform $(uname -s) - skipping shortcut"
      ;;
  esac
fi

head "Done"
say "Launch from the icon, or run:"
say "  \"$VPY\" \"$MAIN_PY\""
echo
