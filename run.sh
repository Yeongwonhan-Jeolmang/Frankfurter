#!/usr/bin/env bash
# Launcher for the Frankfurter desktop app.
# Must be run inside: nix-shell -p python3Full gcc
# (python3Full provides _tkinter; gcc provides libstdc++.so.6 for numpy wheels)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
STAMP="$VENV_DIR/.installed"

# Locate libstdc++ from gcc and add it to LD_LIBRARY_PATH so that
# manylinux numpy/matplotlib wheels can load their C extensions.
GCC_LIBSTDCXX="$(gcc -print-file-name=libstdc++.so.6 2>/dev/null || true)"
if [ -n "$GCC_LIBSTDCXX" ] && [ "$GCC_LIBSTDCXX" != "libstdc++.so.6" ]; then
    GCC_LIBDIR="$(dirname "$GCC_LIBSTDCXX")"
    export LD_LIBRARY_PATH="${GCC_LIBDIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

if [ ! -f "$STAMP" ]; then
    echo "[Frankfurter] First-run: creating Python venv and installing packages..."
    # Remove stale venv if any
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    # Install with --no-user so pip doesn't try a user install (venvs don't support it)
    PIP_USER=0 "$VENV_DIR/bin/pip" install --quiet \
        customtkinter matplotlib pandas httpx Pillow tkcalendar
    touch "$STAMP"
    echo "[Frankfurter] Setup complete."
fi

exec "$VENV_DIR/bin/python3" "$SCRIPT_DIR/main.py"
