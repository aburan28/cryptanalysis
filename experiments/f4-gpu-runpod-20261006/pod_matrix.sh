#!/usr/bin/env bash
# The measurements in RESULT.md, on a Runpod GPU pod.  From the repository:
#
#   B=experiments/f4-gpu-20260925/runpod_bench.py
#   python3 $B up f4 --gpu "NVIDIA GeForce RTX 5090" --min-vcpu 16 \
#       --image runpod/base:1.0.2-ubuntu2404
#   python3 $B sync f4
#   python3 $B ssh f4 -- 'bash /root/cryptanalysis/experiments/f4-gpu-runpod-20261006/pod_matrix.sh /root/receipts'
#   python3 $B fetch f4 /root/receipts /tmp/f4-runpod && python3 $B down f4
#
# Installs Rust 1.99.0 and NVRTC 12 (pip) when missing, builds the suite,
# and writes every report and log under OUT.  The host runs come first, so
# the device is idle for them.  K_0/2^13 m=2 D=6 on the host takes about
# seven minutes; SKIP_HOST_D6=1 leaves it out.
set -euo pipefail

OUT=${1:?usage: pod_matrix.sh OUT}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$OUT"
export LC_ALL=C.UTF-8 PATH="$HOME/.cargo/bin:$PATH"
command -v cargo >/dev/null || curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs |
  sh -s -- -y -q --profile minimal --default-toolchain 1.99.0
python3 -c 'import nvidia.cuda_nvrtc' 2>/dev/null ||
  pip3 install -q --break-system-packages nvidia-cuda-nvrtc-cu12
CA_NVRTC_LIB=$(python3 -c 'import glob, nvidia.cuda_nvrtc as m; print(glob.glob(m.__path__[0] + "/lib/libnvrtc.so.12")[0])')
export CA_NVRTC_LIB

cd "$REPO/suite"
cargo build --release --locked --features gpu-emulator --bin ca-ic \
  --example f4_degree_bench --example f4_matrix_bench --example dreg_sweep \
  --example f4_batch_bench 2>&1 | tail -1
EX=target/release/examples

{
  echo "{"
  echo "  \"gpu\": \"$(nvidia-smi --query-gpu=name,compute_cap,memory.total,driver_version --format=csv,noheader)\","
  echo "  \"cpu_model\": \"$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)\","
  echo "  \"nproc\": $(nproc),"
  echo "  \"cgroup_cpu_max\": \"$(cat /sys/fs/cgroup/cpu.max 2>/dev/null)\","
  echo "  \"rustc\": \"$(rustc --version)\","
  echo "  \"commit\": \"$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)\""
  echo "}"
} >"$OUT/host.json"

# Wall seconds of a command, its output kept in a log.
timed() {
  local name=$1
  shift
  local t0 t1
  t0=$(date +%s.%N)
  "$@" >"$OUT/$name.log" 2>&1
  t1=$(date +%s.%N)
  python3 -c "print(f'$name: {$t1 - $t0:.2f} s')" | tee -a "$OUT/walls.txt"
}

# One matrix per degree, every path asserted against the others.
timed degree-host "$EX/f4_degree_bench" --max-degree 5 --out "$OUT/degree-host"
F4_F2_ECHELON=cuda timed degree-gpu "$EX/f4_degree_bench" --max-degree 5 --out "$OUT/degree-gpu"

# Single large matrices.
for cell in 0:13:2:1234:5 0:9:3:77:5 1:11:2:301:5 1:11:2:301:6 0:13:2:1234:6; do
  IFS=: read -r a n m x d <<<"$cell"
  tag="k${a}n${n}m${m}d${d}"
  if [ "$tag" != k0n13m2d6 ] || [ "${SKIP_HOST_D6:-0}" != 1 ]; then
    timed "matrix-$tag-host" "$EX/f4_matrix_bench" --cell "$a:$n:$m:$x" --degree "$d" \
      --out "$OUT/matrix-$tag-host.json"
  fi
  F4_F2_ECHELON=cuda timed "matrix-$tag-gpu" "$EX/f4_matrix_bench" --cell "$a:$n:$m:$x" \
    --degree "$d" --out "$OUT/matrix-$tag-gpu.json"
done

# The solving-degree sweep, default arguments: the tables must agree.
timed dreg-host "$EX/dreg_sweep"
F4_F2_ECHELON=cuda timed dreg-gpu "$EX/dreg_sweep"
if diff <(grep -v '^n=' "$OUT/dreg-host.log") <(grep -v '^n=' "$OUT/dreg-gpu.log") >/dev/null; then
  echo "dreg tables identical" | tee -a "$OUT/walls.txt"
else
  echo "dreg tables DIFFER" | tee -a "$OUT/walls.txt"
fi

# The per-node path: lockstep searches whose matrices the device decides,
# on the from-scratch engine it implements, beside the default engine.
KIC_F4_INHERIT=0 timed batch-matrixf4 "$EX/f4_batch_bench" --degree 23 --curve-a 1 \
  --targets 1024 --modes rayon,lockstep:cpu,lockstep:cuda --replay-cap 200000 \
  --replay-batch 16384 --out "$OUT/batch-matrixf4"
timed batch-default "$EX/f4_batch_bench" --degree 23 --curve-a 1 --targets 1024 \
  --modes rayon --replay-cap 0 --out "$OUT/batch-default"
cat "$OUT/walls.txt"
