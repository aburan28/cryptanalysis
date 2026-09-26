#!/usr/bin/env bash
# Complete relation collections with the online monitor: collect to the achievable rank,
# solve mod r, descend three fresh targets and verify [log]G = Q.  Paired on curve and
# cell with the factor base varied, over independent target streams.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results
JOBS=${JOBS:-$(nproc)}
OUT=results/collect.jsonl
[ -s "$OUT" ] && exit 0
{
  for ws in 1 2 3; do
    for fam in prefix geometric geomtrace random kertrace; do echo "--n 19 --m 2 --l 5 --family $fam --workload-seed $ws"; done
    for fam in prefix geometric geomtrace random; do echo "--n 19 --m 2 --l 6 --family $fam --workload-seed $ws"; done
    for fam in prefix random; do echo "--n 13 --m 3 --l 3 --family $fam --workload-seed $ws"; done
  done
  for fam in prefix geomtrace random; do echo "--n 23 --m 2 --l 6 --family $fam --workload-seed 1 --max-attempts 800000"; done
} | xargs -P "$JOBS" -I{} sh -c "python3 monitor.py collect {} --mode mxl --report-every 0 --out $OUT > /dev/null"
