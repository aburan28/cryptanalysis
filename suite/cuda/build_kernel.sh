#!/bin/sh
# build_kernel.sh - compile the batched F4 kernel for the GPU generations the
# suite targets and report ptxas's registers, shared memory and spills.
#
#   suite/cuda/build_kernel.sh [NVCC]      (default: $NVCC, else nvcc on PATH)
#
# Needs no GPU: `ecc2k130/scripts/fetch_cuda.sh` assembles a CUDA 13.3 nvcc
# from NVIDIA's pip wheels.  Fails if an architecture spills or yields no
# cubin.  Also writes the PTX that `CA_F4_PTX` can hand the host driver on a
# machine without NVRTC.  Output goes to $OUT (default: a temporary dir).
set -eu

NVCC=${1:-${NVCC:-nvcc}}
DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
OUT=${OUT:-$(mktemp -d)}
mkdir -p "$OUT"
status=0

for arch in sm_75 sm_80 sm_86 sm_89 sm_90 sm_120; do
    cubin="$OUT/f4_gf2_$arch.cubin"
    log=$("$NVCC" -arch="$arch" -O3 -Xptxas -v -cubin -o "$cubin" "$DIR/f4_gf2_kernel.cu" 2>&1) || {
        echo "$log"
        echo "$arch: compile failed"
        status=1
        continue
    }
    echo "$arch: $(echo "$log" | grep -E 'registers|spill' | sed 's/ptxas info *: //' | tr '\n' ' ')"
    if [ ! -s "$cubin" ]; then
        echo "$arch: no cubin"
        status=1
    fi
    if echo "$log" | grep -Eq '[1-9][0-9]* bytes spill'; then
        echo "$arch: spills"
        status=1
    fi
done

"$NVCC" -arch=compute_75 -O3 -ptx -o "$OUT/f4_gf2_kernel.ptx" "$DIR/f4_gf2_kernel.cu"
echo "ptx: $OUT/f4_gf2_kernel.ptx"
exit $status
