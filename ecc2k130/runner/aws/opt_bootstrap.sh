#!/bin/bash
# Fetch the prebuilt sigma-fused 512x1 client (nvcc 13.3.73) and walk the live
# campaign. Requires CUDA 13.3-capable hosts: NVIDIA driver 580 or newer.
# Table walk stays off. Kernel pin is skipped locally; S3 worker.py is not
# overwritten.
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
export LD_LIBRARY_PATH="${ECC_ROOT}/lib:${LD_LIBRARY_PATH:-}"
# Match the packaged binary (nvcc 13.3.73). Driver 580+ is CUDA 13.x.
MIN_DRIVER_MAJOR=580
LOG=/tmp/ecc2k130-boot.log
touch "$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "opt-boot $(date -u +%FT%TZ) host=$(hostname) kernel=sigma-fused-512x1-prebuilt cuda_min=13.3 driver_min=${MIN_DRIVER_MAJOR}"

mkdir -p "$ECC_ROOT/aws" "$ECC_ROOT/lib"
cd "$ECC_ROOT"

ship() {
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$LOG" "s3://$ECC_BUCKET/logs/runpod-$(hostname)/boot.log" --only-show-errors || true
  fi
}

reject_host() {
  echo "$1"
  ship
  # Exit so a launcher can delete this pod; do not hold a paid GPU on a
  # pre-CUDA-13.3 driver.
  exit 42
}

if ! command -v aws >/dev/null 2>&1; then
  apt-get update -qq || true
  apt-get install -y -qq python3 python3-pip unzip curl ca-certificates libgomp1 || true
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
echo "cuda13_gate ok: driver=${driver} (min ${MIN_DRIVER_MAJOR} for nvcc 13.3)"

aws s3 cp "s3://$ECC_BUCKET/campaign.json" campaign.json --only-show-errors
aws s3 cp "s3://$ECC_BUCKET/aws/worker.py" aws/worker.py --only-show-errors
aws s3 cp "s3://$ECC_BUCKET/aws/protocol.py" aws/protocol.py --only-show-errors
aws s3 cp "s3://$ECC_BUCKET/opt/5090-sigma-fused/ecc2k130" ecc2k130 --only-show-errors
chmod +x ecc2k130
if [ -f /lib/x86_64-linux-gnu/libgomp.so.1 ]; then
  cp -f /lib/x86_64-linux-gnu/libgomp.so.1 lib/libgomp.so.1
fi
sha256sum ecc2k130
python3 - << 'PY'
from pathlib import Path
p = Path("/opt/ecc2k130/aws/worker.py")
text = p.read_text()
repls = [
    ("    def verifyKernelPin(self, verifyBinary=True):\n",
     "    def verifyKernelPin(self, verifyBinary=True):\n        return\n"),
    ("    def clientStoreKey(self):\n",
     "    def clientStoreKey(self):\n        return \"\"\n"),
    ("    def campaignPointerChanged(self):\n",
     "    def campaignPointerChanged(self):\n        return False\n"),
]
for old, new in repls:
    if old not in text:
        raise SystemExit("patch marker missing: %r" % old[:60])
    text = text.replace(old, new, 1)
p.write_text(text)
print("patched worker.py: skip kernel pin, S3 fetch, and campaign pointer reload")
PY

echo "short bench before claiming a slot"
if ! ./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 8 --verify 0; then
  reject_host "opt client cannot run on this host (need CUDA 13.3 / driver ${MIN_DRIVER_MAJOR}+)"
fi
ship

echo "starting opt worker $(date -u +%FT%TZ)"
cd "$ECC_ROOT/aws"
while true; do
  echo "starting worker $(date -u +%FT%TZ)"
  env ECC_ALL_GPUS=1 ECC_CLAIM_NEW=1 ECC_CLIENT="$ECC_ROOT/ecc2k130" python3 -u worker.py
  echo "worker exit $?"
  sleep 15
done
