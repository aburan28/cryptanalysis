#!/usr/bin/env bash
# gpu_bench.py on a Modal GPU with many cores, through cloud/modal_run.py.
#
#   experiments/f4-gpu-20260925/run_modal.sh                  # H100, 32 cores
#   GPU=RTX-PRO-6000 CPU=48 experiments/f4-gpu-20260925/run_modal.sh
#   experiments/f4-gpu-20260925/run_modal.sh --targets 256    # more gpu_bench.py flags
#
# Credentials and the Modal client as in cloud/README.md.  The container
# builds suite/ from this checkout, runs gpu_bench.py, and the receipts come
# back to receipts/gpu/<gpu>-cpu<n>-<UTC time>/ (or receipts/gpu/$NAME/) even
# when a check fails; the exit status is gpu_bench.py's.
#
# Modal reserves CPU in physical cores, so rayon gets two threads a core
# unless THREADS says otherwise.  NVRTC comes from the image's CUDA 12.8,
# whose SASS any CUDA 12 or later driver loads.
set -euo pipefail

gpu=${GPU:-H100}
cpu=${CPU:-32}
memory=${MEMORY_GIB:-32}
threads=${THREADS:-$((2 * cpu))}
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
slug=$(printf '%s' "$gpu" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-')
name=${NAME:-$slug-cpu$cpu-$(date -u +%Y%m%dT%H%M%SZ)}
out="experiments/f4-gpu-20260925/receipts/gpu/$name"
build="cargo build --release --locked --features gpu-emulator --bin ca-ic"
build+=" --example f4_batch_bench --example groebner_stage_bench"
bench="python3 ../experiments/f4-gpu-20260925/gpu_bench.py --out ../$out"
for arg in "$@"; do
  bench+=" $(printf '%q' "$arg")"
done

cd "$repo"
exec python3 cloud/modal_run.py run --image cuda --gpu "$gpu" --cpu "$cpu" \
  --memory "$memory" --timeout 7200 --env "RAYON_NUM_THREADS=$threads" \
  --env CA_NVRTC_LIB=/usr/local/cuda/lib64/libnvrtc.so.12 \
  --out "$out" -- "cd suite && $build && $bench"
