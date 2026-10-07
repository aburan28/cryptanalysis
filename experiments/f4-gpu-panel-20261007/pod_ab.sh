#!/usr/bin/env bash
# The measurements in README.md, on a CUDA host: the large-matrix
# elimination before this change (BASE, the merged #119) and after it (this
# checkout), alternated on the same device.  From the repository:
#
#   cloud/runpod_pod.py run panel --gpu "NVIDIA GeForce RTX 5090" \
#       --out experiments/f4-gpu-panel-20261007/receipts -- \
#       'bash experiments/f4-gpu-panel-20261007/pod_ab.sh experiments/f4-gpu-panel-20261007/receipts'
#
# REPS (default 3) sets the timed repeats and PROFILE_CELLS the
# a:n:m:x:d cells profiled per kernel (default the two D=6 cells).
# Needs Rust and NVRTC (cloud/pod_env.sh), git and network to fetch BASE.
set -euo pipefail

OUT=${1:?usage: pod_ab.sh OUT}
BASE=${BASE:-4eb0194deee645de1494d05a1fbd85e90fe2c14b}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
cd "$REPO"
# shellcheck source=cloud/pod_env.sh
source cloud/pod_env.sh

EXAMPLES=(--example f4_matrix_bench --example f4_degree_bench --example dreg_sweep)
(cd suite && cargo build --release --locked "${EXAMPLES[@]}" 2>&1 | tail -1)
NEW=$REPO/suite/target/release/examples

base_dir=/root/panel-base
if [ ! -x "$base_dir/suite/target/release/examples/f4_matrix_bench" ]; then
  rm -rf "$base_dir" && git init -q "$base_dir"
  git -C "$base_dir" fetch -q --depth=1 https://github.com/aburan28/cryptanalysis.git "$BASE"
  git -C "$base_dir" checkout -q FETCH_HEAD
  (cd "$base_dir/suite" && cargo build --release --locked --example f4_matrix_bench 2>&1 | tail -1)
fi
OLD=$base_dir/suite/target/release/examples

{
  echo "{"
  echo "  \"gpu\": \"$(nvidia-smi --query-gpu=name,compute_cap,memory.total,driver_version --format=csv,noheader)\","
  echo "  \"cpu_model\": \"$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)\","
  echo "  \"cpus\": \"${RUNPOD_CPU_COUNT:-$(nproc)}\","
  echo "  \"rustc\": \"$(rustc --version)\","
  echo "  \"base\": \"$(git -C "$base_dir" rev-parse HEAD)\""
  echo "}"
} >"$OUT/host.json"

# One process per matrix: F4_F2_ECHELON_VERBOSE prints the device's own
# upload, elimination and download, after the one-time start-up.
CELLS="0:13:2:1234:5 0:9:3:77:5 1:11:2:301:5 1:11:2:301:6 0:13:2:1234:6"
for rep in $(seq "${REPS:-3}"); do
  for cell in $CELLS; do
    IFS=: read -r a n m x d <<<"$cell"
    tag="k${a}n${n}m${m}d${d}"
    for side in old new; do
      bin=$OLD
      [ "$side" = new ] && bin=$NEW
      F4_F2_ECHELON=cuda F4_F2_ECHELON_VERBOSE=1 "$bin/f4_matrix_bench" --cell "$a:$n:$m:$x" \
        --degree "$d" --out "$OUT/matrix-$tag-$side-$rep.json" >"$OUT/matrix-$tag-$side-$rep.log" 2>&1
      echo "$tag $side $rep: $(grep -h '^F4_F2_ECHELON:' "$OUT/matrix-$tag-$side-$rep.log" | tail -1)"
    done
  done
done | tee "$OUT/walls.txt"

# Where the device time goes, each launch synchronised.
for cell in ${PROFILE_CELLS:-1:11:2:301:6 0:13:2:1234:6}; do
  IFS=: read -r a n m x d <<<"$cell"
  tag="k${a}n${n}m${m}d${d}"
  for side in old new; do
    bin=$OLD
    [ "$side" = new ] && bin=$NEW
    F4_F2_ECHELON=cuda F4_F2_ECHELON_PROFILE=1 "$bin/f4_matrix_bench" --cell "$a:$n:$m:$x" \
      --degree "$d" >"$OUT/profile-$tag-$side.log" 2>&1
  done
done

# Every path agrees with the new kernel, and the sweep's tables are the host's.
F4_F2_ECHELON=cuda "$NEW/f4_degree_bench" --max-degree 5 --out "$OUT/degree-new" >"$OUT/degree-new.log" 2>&1
F4_F2_ECHELON=host "$NEW/dreg_sweep" >"$OUT/dreg-host.log" 2>&1
F4_F2_ECHELON=cuda "$NEW/dreg_sweep" >"$OUT/dreg-new.log" 2>&1
if diff <(grep -v '^n=' "$OUT/dreg-host.log") <(grep -v '^n=' "$OUT/dreg-new.log") >/dev/null; then
  echo "dreg tables identical" | tee -a "$OUT/walls.txt"
else
  echo "dreg tables DIFFER" | tee -a "$OUT/walls.txt"
fi
