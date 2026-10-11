#!/usr/bin/env bash
# The trace-zero geometric progression (family geomtrace) on the same curves and
# workloads as sweep.sh and sweep_sym.sh, so its rows pair with every other family.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results traces
JOBS=${JOBS:-$(nproc)}
NS=13,19,23,29,31,37,41,43,47

python3 profile.py --n $NS --m 2 --l 3-9 --families geomtrace \
  --seeds 1,2 --targets 48 --planted 8 --sat --max-vars 18 --jobs "$JOBS" --skip-existing \
  --out results/geomtrace_m2.jsonl --trace traces/geomtrace_m2.jsonl
python3 profile.py --n $NS --m 3 --l 2-4 --families geomtrace \
  --seeds 1,2 --targets 32 --planted 6 --sat --max-vars 12 --jobs "$JOBS" --skip-existing \
  --out results/geomtrace_m3.jsonl --trace traces/geomtrace_m3.jsonl
python3 profile.py --formulation sym --n $NS --m 2 --l 3-9 \
  --families geomtrace --seeds 1,2 --targets 48 --planted 8 --max-vars 26 --jobs "$JOBS" --skip-existing \
  --out results/geomtrace_sym_m2.jsonl --trace traces/geomtrace_sym_m2.jsonl
python3 profile.py --formulation sym --n 23,29,31,37,41,43,47 --m 3 --l 2-4 \
  --families geomtrace --seeds 1,2 --targets 32 --planted 6 --max-vars 22 --max-cols 30000 --jobs "$JOBS" --skip-existing \
  --out results/geomtrace_sym_m3.jsonl --trace traces/geomtrace_sym_m3.jsonl
python3 profile.py --formulation sym --n 13,19 --m 3 --l 2-3 \
  --families geomtrace --seeds 1,2 --targets 32 --planted 6 --max-vars 22 --max-cols 30000 --jobs "$JOBS" --skip-existing \
  --out results/geomtrace_sym_m3.jsonl --trace traces/geomtrace_sym_m3.jsonl
