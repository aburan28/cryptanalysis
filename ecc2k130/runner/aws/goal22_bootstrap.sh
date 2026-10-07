#!/bin/bash
# Build and run the measured goal22 / table-walk 22B profile on CUDA 13.3+.
# Target: RTX PRO 6000 Blackwell (~22.1 B it/s). Campaign: ecc2k130-table8-22b-v1.
# Do not use the 5090 sigma-fused ~5 B kernel.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
export ECC_ROOT="${ECC_ROOT:-/opt/ecc2k130}"
export ECC_BUCKET="${ECC_BUCKET:-ecc2k130-590183823895}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
export PYTHONUNBUFFERED=1
export ECC_ALLOW_LEGACY_STORAGE=1
export ECC_ALL_GPUS=1
export ECC_CLAIM_NEW=1
export ECC_SKIP_KERNEL_PIN=1
export ECC_PREFIX="${ECC_PREFIX:-campaigns/ecc2k130-table8-22b-v1}"
export LD_LIBRARY_PATH="${ECC_ROOT}/lib:${LD_LIBRARY_PATH:-}"
MIN_DRIVER_MAJOR=580
OPT_PREFIX="opt/pro6000-goal22"
LOG=/tmp/ecc2k130-boot.log
touch "$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "goal22-boot $(date -u +%FT%TZ) host=$(hostname) kernel=pro6000-goal22-22b cuda_min=13.3 driver_min=${MIN_DRIVER_MAJOR} prefix=${ECC_PREFIX}"

mkdir -p "$ECC_ROOT/aws" "$ECC_ROOT/lib" "$ECC_ROOT/build"
cd "$ECC_ROOT"

ship() {
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$LOG" "s3://$ECC_BUCKET/logs/runpod-$(hostname)/boot.log" --only-show-errors || true
  fi
}

reject_host() {
  echo "$1"
  ship
  exit 42
}

if ! command -v aws >/dev/null 2>&1; then
  apt-get update -qq || true
  apt-get install -y -qq python3 python3-pip unzip curl ca-certificates libgomp1 build-essential || true
  pip3 install -q awscli || true
fi
if ! command -v aws >/dev/null 2>&1; then
  curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
fi
ship
( while true; do sleep 20; ship; done ) &

for i in $(seq 1 60); do
  nvidia-smi -L >/dev/null 2>&1 && break
  sleep 5
done
nvidia-smi -L || true
nvidia-smi --query-gpu=name,driver_version,compute_cap,clocks.max.sm,power.limit --format=csv || true

driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | tr -d '[:space:]')"
if ! python3 -c "import sys; d='${driver}'.split('.',1)[0]; sys.exit(0 if d.isdigit() and int(d)>=${MIN_DRIVER_MAJOR} else 1)"; then
  reject_host "driver below ${MIN_DRIVER_MAJOR} (got '${driver}'); need CUDA 13.3+ / driver ${MIN_DRIVER_MAJOR}+"
fi
gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | tr -d '\n')"
echo "cuda13_gate ok: driver=${driver} gpu=${gpu_name}"
case "$gpu_name" in
  *PRO\ 6000*|*RTX\ PRO\ 6000*) echo "gpu_class=pro6000" ;;
  *) echo "warning: goal22 was measured on RTX PRO 6000; got ${gpu_name}" ;;
esac

# Prefer a prebuilt binary if present; otherwise build with CUDA 13.3.73.
HAVE_BIN=0
if aws s3 cp "s3://$ECC_BUCKET/${OPT_PREFIX}/ecc2k130" "$ECC_ROOT/ecc2k130" --only-show-errors; then
  chmod +x "$ECC_ROOT/ecc2k130"
  if "$ECC_ROOT/ecc2k130" --curve 131 --packed --bench --steps 1024 --launches 2 --verify 0; then
    HAVE_BIN=1
    echo "using prebuilt ${OPT_PREFIX}/ecc2k130"
  else
    echo "prebuilt binary failed smoke; will rebuild"
    rm -f "$ECC_ROOT/ecc2k130"
  fi
fi

if [ "$HAVE_BIN" != 1 ]; then
  apt-get update -qq || true
  apt-get install -y -qq python3 python3-pip unzip curl ca-certificates libgomp1 build-essential g++ || true
  pip3 install -q awscli pip || true
  aws s3 cp "s3://$ECC_BUCKET/${OPT_PREFIX}/source.tgz" /tmp/goal22-source.tgz --only-show-errors
  rm -rf /tmp/goal22-src
  mkdir -p /tmp/goal22-src
  tar xzf /tmp/goal22-source.tgz -C /tmp/goal22-src
  SRC="$(find /tmp/goal22-src -maxdepth 2 -type d -name ecc2k130 | head -1)"
  [ -n "$SRC" ] || reject_host "source.tgz missing ecc2k130 tree"
  cd "$SRC"
  sh scripts/fetch_cuda.sh "$ECC_ROOT/build/cuda-13.3"
  export CUDA13_HOME="$ECC_ROOT/build/cuda-13.3"
  export PATH="$CUDA13_HOME/bin:$PATH"
  nvcc --version
  make -B gpu-goal22 NVCC="$CUDA13_HOME/bin/nvcc"
  install -m 755 ecc2k130 "$ECC_ROOT/ecc2k130"
  sha256sum "$ECC_ROOT/ecc2k130" | tee "$ECC_ROOT/ecc2k130.sha256"
  aws s3 cp "$ECC_ROOT/ecc2k130" "s3://$ECC_BUCKET/${OPT_PREFIX}/ecc2k130" --only-show-errors || true
  aws s3 cp "$ECC_ROOT/ecc2k130.sha256" "s3://$ECC_BUCKET/${OPT_PREFIX}/ecc2k130.sha256" --only-show-errors || true
  cd "$ECC_ROOT"
fi

aws s3 cp "s3://$ECC_BUCKET/aws/worker.py" "$ECC_ROOT/aws/worker.py" --only-show-errors
aws s3 cp "s3://$ECC_BUCKET/aws/protocol.py" "$ECC_ROOT/aws/protocol.py" --only-show-errors
# Local campaign copy for debugging; worker loads from ECC_PREFIX.
aws s3 cp "s3://$ECC_BUCKET/${ECC_PREFIX}/campaign.json" "$ECC_ROOT/campaign.json" --only-show-errors
if [ -f /lib/x86_64-linux-gnu/libgomp.so.1 ]; then
  cp -f /lib/x86_64-linux-gnu/libgomp.so.1 "$ECC_ROOT/lib/libgomp.so.1"
fi
sha256sum "$ECC_ROOT/ecc2k130"

echo "bench before claiming a slot (expect ~20+ B it/s on PRO 6000)"
if ! "$ECC_ROOT/ecc2k130" --curve 131 --packed --bench --steps 1024 --launches 16 --verify 0; then
  reject_host "goal22 client cannot run on this host"
fi
ship

echo "starting goal22 worker $(date -u +%FT%TZ) prefix=${ECC_PREFIX}"
cd "$ECC_ROOT/aws"
while true; do
  echo "starting worker $(date -u +%FT%TZ)"
  env ECC_ALL_GPUS=1 ECC_CLAIM_NEW=1 ECC_PREFIX="$ECC_PREFIX" \
      ECC_CLIENT="$ECC_ROOT/ecc2k130" python3 -u worker.py
  echo "worker exit $?"
  sleep 15
done
