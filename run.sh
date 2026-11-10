#!/usr/bin/env bash
# Launcher for the Frankfurter desktop app on NixOS.
#
# Easiest: let Nix provide PyQt6 (pip wheels of Qt need system libraries that
# NixOS doesn't expose at the usual paths):
#
#   nix-shell -p 'python3.withPackages (ps: [ ps.pyqt6 ps.matplotlib ps.pandas ps.httpx ])' \
#             --run 'bash run.sh'
#
# If PyQt6 is already importable, the app starts straight away. Otherwise a
# venv is created and the requirements are pip-installed into it.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
STAMP="$VENV_DIR/.installed-qt"

if python3 -c "import PyQt6.QtWidgets, matplotlib, pandas, httpx" 2>/dev/null; then
    exec python3 "$SCRIPT_DIR/main.py"
fi

# Locate libstdc++ from gcc and add it to LD_LIBRARY_PATH so that
# manylinux numpy/matplotlib wheels can load their C extensions.
GCC_LIBSTDCXX="$(gcc -print-file-name=libstdc++.so.6 2>/dev/null || true)"
if [ -n "$GCC_LIBSTDCXX" ] && [ "$GCC_LIBSTDCXX" != "libstdc++.so.6" ]; then
    GCC_LIBDIR="$(dirname "$GCC_LIBSTDCXX")"
    export LD_LIBRARY_PATH="${GCC_LIBDIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

if [ ! -f "$STAMP" ]; then
    echo "[Frankfurter] First-run: creating Python venv and installing packages..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    PIP_USER=0 "$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
    touch "$STAMP"
    echo "[Frankfurter] Setup complete."
fi

exec "$VENV_DIR/bin/python3" "$SCRIPT_DIR/main.py"
