#!/bin/sh
# fetch_cuda.sh - assemble a CUDA 13.3 compiler from NVIDIA's pip wheels.
#
#   ecc2k130/scripts/fetch_cuda.sh [DIR]      (default ecc2k130/build/cuda)
#
# The kernel's products are `clmad` instructions, which PTX 9.3 / CUDA 13.3
# introduced, so an older system toolkit cannot build it.  The wheels carry
# nvcc, cicc, ptxas, the runtime headers and libdevice; no driver, no GPU and
# no system install are needed to compile, which is what lets CI check that
# the kernel still builds and what it costs in registers.  Prints the
# directory; put "$DIR/bin" on PATH or pass NVCC="$DIR/bin/nvcc" to make.
#
# The versions are pinned because they are the ones the measurements in
# README.md were made with (CUDA 13.3.73).
set -eu

DIR=${1:-"$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)/build/cuda"}
NVCC_VERSION=13.3.73
RUNTIME_VERSION=13.3.29
CCCL_VERSION=13.3.3.4.1

if [ -x "$DIR/bin/nvcc" ] && [ -x "$DIR/nvvm/bin/cicc" ]; then
    echo "$DIR"
    exit 0
fi

WHEELS="$DIR/wheels"
mkdir -p "$WHEELS/x" "$DIR"
pip download -q --no-deps -d "$WHEELS" \
    "nvidia-cuda-nvcc==$NVCC_VERSION" "nvidia-cuda-crt==$NVCC_VERSION" \
    "nvidia-nvvm==$NVCC_VERSION" "nvidia-cuda-runtime==$RUNTIME_VERSION" \
    "nvidia-cuda-cccl==$CCCL_VERSION"
for w in "$WHEELS"/*.whl; do
    unzip -q -o "$w" -d "$WHEELS/x"
done
cp -r "$WHEELS/x/nvidia/cu13/." "$DIR/"
chmod +x "$DIR"/bin/* "$DIR"/nvvm/bin/*
"$DIR/bin/nvcc" --version >/dev/null
echo "$DIR"
