#!/usr/bin/env bash
set -euo pipefail
OUT=${1:?usage: pod_query_ab.sh OUTPUT_DIRECTORY}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$(dirname "$OUT")"
OUT=$(python3 -c 'import os,sys;print(os.path.abspath(sys.argv[1]))' "$OUT")
cd "$REPO"
# shellcheck source=cloud/pod_env.sh
source cloud/pod_env.sh
(cd suite && cargo build --release --locked --example f4_query_bench)
python3 experiments/f4-gpu-query-20261008/query_ab.py \
    --binary suite/target/release/examples/f4_query_bench \
    --output "$OUT" --reps "${REPS:-3}" --timeout "${QUERY_TIMEOUT:-180}"
