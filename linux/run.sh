#!/bin/bash
# Starts the game; the options are those of run-linux.py (e.g. ./run.sh --fullscreen).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
python3 run-linux.py --prompt --follow "$@"
rc=$?
if [ $rc -ne 0 ] && [ -t 0 ]; then read -rp "Press Enter to close..."; fi
exit $rc
