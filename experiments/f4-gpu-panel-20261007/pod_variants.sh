#!/usr/bin/env bash
# Per-kernel profiles of kernel-source variants on one CUDA device: each
# variant is a copy of suite/cuda/f4_gf2_echelon.cuh built into its own
# f4_matrix_bench, then the D=6 cells are profiled and the D=5 cells timed,
# variants alternated.  A variant may be a diagnostic that breaks the
# answer (to bound what a step costs); its rank is in its log.
#
#   cloud/runpod_pod.py run variants --gpu "NVIDIA GeForce RTX 4090" \
#       --out experiments/f4-gpu-panel-20261007/receipts/NAME -- \
#       'bash experiments/f4-gpu-panel-20261007/pod_variants.sh \
#        experiments/f4-gpu-panel-20261007/receipts/NAME name=path.cuh ...'
# REPS and PROFILE_CELLS as in pod_ab.sh.
set -euo pipefail

OUT=${1:?usage: pod_variants.sh OUT NAME=CUH...}
shift
REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
cd "$REPO"
# shellcheck source=cloud/pod_env.sh
source cloud/pod_env.sh

CUH=suite/cuda/f4_gf2_echelon.cuh
BIN=/root/variants
mkdir -p "$BIN"
cp "$CUH" "$BIN/checkout.cuh"
NAMES=()
for spec in "$@"; do
  name=${spec%%=*}
  cp "${spec#*=}" "$CUH"
  sha256sum "$CUH" | sed "s|$CUH|$name|" >>"$OUT/variants.sha256"
  (cd suite && cargo build --release --locked --example f4_matrix_bench 2>&1 | tail -1)
  cp suite/target/release/examples/f4_matrix_bench "$BIN/$name"
  NAMES+=("$name")
done
cp "$BIN/checkout.cuh" "$CUH"

{
  echo "{"
  echo "  \"gpu\": \"$(nvidia-smi --query-gpu=name,compute_cap,memory.total,driver_version --format=csv,noheader)\","
  echo "  \"cpu_model\": \"$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)\","
  echo "  \"cpus\": \"${RUNPOD_CPU_COUNT:-$(nproc)}\","
  echo "  \"rustc\": \"$(rustc --version)\""
  echo "}"
} >"$OUT/host.json"

for rep in $(seq "${REPS:-3}"); do
  for cell in 0:13:2:1234:5 0:9:3:77:5 1:11:2:301:5; do
    IFS=: read -r a n m x d <<<"$cell"
    tag="k${a}n${n}m${m}d${d}"
    for name in "${NAMES[@]}"; do
      F4_F2_ECHELON=cuda F4_F2_ECHELON_VERBOSE=1 "$BIN/$name" --cell "$a:$n:$m:$x" --degree "$d" \
        >"$OUT/matrix-$tag-$name-$rep.log" 2>&1 || true
      echo "$tag $name $rep: $(grep -h '^F4_F2_ECHELON:' "$OUT/matrix-$tag-$name-$rep.log" | tail -1)"
    done
  done
done | tee "$OUT/walls.txt"

for cell in ${PROFILE_CELLS:-1:11:2:301:6 0:13:2:1234:6}; do
  IFS=: read -r a n m x d <<<"$cell"
  tag="k${a}n${n}m${m}d${d}"
  for name in "${NAMES[@]}"; do
    F4_F2_ECHELON=cuda F4_F2_ECHELON_PROFILE=1 "$BIN/$name" --cell "$a:$n:$m:$x" --degree "$d" \
      >"$OUT/profile-$tag-$name.log" 2>&1 || true
    echo "$tag $name: $(grep -h 'f4e_panel_block\|rank' "$OUT/profile-$tag-$name.log" | tr '\n' ' ')"
  done
done | tee -a "$OUT/walls.txt"
