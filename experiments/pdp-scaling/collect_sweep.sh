#!/usr/bin/env bash
# Paired relation-collection sweep: every configuration sees the same targets
# (same --seed per cell), so the ratios between configurations are paired.
#
#   collect_sweep.sh OUT.jsonl CONFIG...      CONFIG = engine:order:trace(0|1)
#
# Cells are (n, l, calls); the oracle is on everywhere (l <= 7 here).
set -euo pipefail
out=$1
shift
cells=${CELLS:-"17:4:800 17:5:800 19:5:800 19:6:600 23:6:600 23:7:300"}
for cell in $cells; do
  IFS=: read -r n l calls <<<"$cell"
  for cfg in "$@"; do
    IFS=: read -r engine order trace <<<"$cfg"
    flag=""
    [ "$trace" = 1 ] && flag="--trace"
    python3 collect.py --n "$n" --l "$l" --calls "$calls" --seed 21 --oracle \
      --engine "$engine" --order "$order" $flag --out "$out" >/dev/null
    echo "done n=$n l=$l $cfg"
  done
done
