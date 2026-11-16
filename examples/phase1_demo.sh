#!/bin/sh
# Phase 1 demonstration, as a POSIX shell session. Same scenario as phase1_demo.py.
#
#   sh examples/phase1_demo.sh OUTPUT_DIR
#
# Needs `bbim` on the PATH (for example inside `uv run`, or an activated environment).
set -eu
out=${1:?usage: phase1_demo.sh OUTPUT_DIR}
mkdir -p "$out"
f="$out/casa.bbim"

bbim new "$f" --name Casa --force
bbim level add "$f" "Piano terra" 0
bbim level add "$f" "Primo piano" 3.00

# Four 30 cm walls, ground floor to first floor; shared end points give mitred corners.
set -- --thickness 0.30 --base "Piano terra" --top "Primo piano"
south=$(bbim wall add "$f" --start 0 0 --end 6 0 "$@" --quiet)
bbim wall add "$f" --start 6 0 --end 6 4 "$@" --quiet >/dev/null
north=$(bbim wall add "$f" --start 6 4 --end 0 4 "$@" --quiet)
bbim wall add "$f" --start 0 4 --end 0 0 "$@" --quiet >/dev/null

bbim door add "$f" "$south" --position 1.50 --width 0.90 --height 2.10 --swing left --hinge start
bbim window add "$f" "$north" --position 3 --width 1.20 --height 1.40 --sill 0.90
bbim wall joins "$f"

bbim ifc export "$f" "$out/casa-before.ifc" --validate
bbim plan "$f" "Piano terra" "$out/casa-before.svg" --scale 1:50 --paper A4

bbim level move "$f" "Primo piano" 3.20
bbim wall list "$f"

bbim ifc export "$f" "$out/casa-after.ifc" --validate
bbim plan "$f" "Piano terra" "$out/casa-after.svg" --scale 1:50 --paper A4
