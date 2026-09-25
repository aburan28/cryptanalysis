#!/usr/bin/env bash
# The symmetric formulation (unknowns e_k in V^(k)) on the same curves and workloads
# as sweep.sh.  Factor bases whose sum of dim V^(k) exceeds --max-vars are skipped
# and logged, since that size is itself the measured effect.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results traces
JOBS=${JOBS:-$(nproc)}
FAMILIES=prefix,geometric,random,normal,kertrace,invariant
COMMON="--jobs $JOBS --skip-existing"

python3 profile.py --formulation sym --n 13,19,23,29,31,37,41,43,47 --m 2 --l 3-9 \
  --families $FAMILIES --seeds 1,2 --targets 48 --planted 8 --max-vars 26 $COMMON \
  --out results/sym_m2.jsonl --trace traces/sym_m2.jsonl

# three summands: overdetermined fields first; at n = 13, 19 the l = 4 systems have more
# unknowns (21) than equations and XL runs into the matrix budget, so stop at l = 3 there
python3 profile.py --formulation sym --n 23,29,31,37,41,43,47 --m 3 --l 2-4 \
  --families $FAMILIES --seeds 1,2 --targets 32 --planted 6 --max-vars 22 --max-cols 30000 $COMMON \
  --out results/sym_m3.jsonl --trace traces/sym_m3.jsonl
python3 profile.py --formulation sym --n 13,19 --m 3 --l 2-3 \
  --families $FAMILIES --seeds 1,2 --targets 32 --planted 6 --max-vars 22 --max-cols 30000 $COMMON \
  --out results/sym_m3.jsonl --trace traces/sym_m3.jsonl
