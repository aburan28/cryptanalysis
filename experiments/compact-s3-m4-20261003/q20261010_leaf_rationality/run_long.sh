#!/bin/sh
# Reproduce the two frozen extended Q1434 ordinary solver runs.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../../.." && pwd)
STAGE="$ROOT/experiments/compact-s3-m4-20261003"
BIN=${1:-/private/tmp/q1434_insearch}
cd "$ROOT"
set +e
"$BIN" /private/tmp/q1430_n53_ordinary.cnf \
  /private/tmp/q1430_n53_ordinary.map \
  "$STAGE/q20261010_final_link/n53_ordinary.targets" \
  "$STAGE" "$ROOT/ecc2k130/codegen" \
  allpos satpivot selector 20 sat 3 100000 120 \
  > "$HERE/n53_allpos_leaf_sat_long.log"
STATUS=$?
case "$STATUS" in 0|10|20) ;; *) exit "$STATUS" ;; esac
"$BIN" /private/tmp/q1430_ordinary.cnf \
  /private/tmp/q1430_ordinary.map \
  "$STAGE/q20261010_final_link/n83_ordinary.targets" \
  "$STAGE" "$ROOT/ecc2k130/codegen" \
  allpos satpivot selector 100 sat 5 100000 120 \
  > "$HERE/n83_allpos_leaf_sat_long.log"
STATUS=$?
case "$STATUS" in 0|10|20) ;; *) exit "$STATUS" ;; esac
