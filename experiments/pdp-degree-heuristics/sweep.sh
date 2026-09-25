#!/usr/bin/env bash
# The measured grids behind README.md.  Each line appends one receipt per
# (factor base, workload) run; delete a results file to re-measure it.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results traces
JOBS=${JOBS:-$(nproc)}
FAMILIES=prefix,geometric,random,normal,kertrace,invariant
NS=13,19,23,29,31,37,41,43,47

# two summands: the degree-2 descent, l = 3..9 (N <= 18)
[ -s results/m2.jsonl ] || python3 profile.py --n $NS --m 2 --l 3-9 --families $FAMILIES \
  --seeds 1,2 --targets 48 --planted 8 --sat --dreg --dreg-targets 3 --dreg-max 7 \
  --max-vars 18 --jobs "$JOBS" --out results/m2.jsonl --trace traces/m2.jsonl

# three summands: the degree-6 descent, l = 2..4 (N <= 12)
[ -s results/m3.jsonl ] || python3 profile.py --n $NS --m 3 --l 2-4 --families $FAMILIES \
  --seeds 1,2 --targets 32 --planted 6 --sat --max-vars 12 --jobs "$JOBS" \
  --out results/m3.jsonl --trace traces/m3.jsonl

# three summands at l = 5 (N = 15), where each query costs ~10^10 word operations
[ -s results/m3_l5.jsonl ] || python3 profile.py --n 31,37,41,47 --m 3 --l 5 \
  --families prefix,geometric,random --seeds 1 --targets 10 --planted 2 --max-vars 15 \
  --jobs "$JOBS" --out results/m3_l5.jsonl --trace traces/m3_l5.jsonl
