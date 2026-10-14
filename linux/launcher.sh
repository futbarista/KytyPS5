#!/bin/bash
# The settings window (launcher-linux.py): game folder, resolution, fullscreen, console language, precompile.
cd "$(dirname "$(readlink -f "$0")")" && exec python3 launcher-linux.py "$@"
