#!/bin/bash
# Every shader and pipeline of the game into the static pipeline cache: about an hour or two on this PC's cores
# (it resumes when interrupted). Options: those of precompile-linux.py.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
python3 precompile-linux.py "$@"
rc=$?
if [ -t 0 ]; then echo; read -rp "Press Enter to close..."; fi
exit $rc
