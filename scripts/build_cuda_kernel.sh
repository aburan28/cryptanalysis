#!/bin/sh
# build_cuda_kernel.sh - compile the CUDA rho kernel to PTX and a cubin and
# report its register and local-memory usage.
#
# This does NOT need a GPU, and it does not need a full CUDA installation:
# with --fetch it assembles the pieces it needs (headers, libdevice, ptxas)
# from NVIDIA's pip wheels into a scratch directory and compiles with clang.
# That makes "does the kernel still compile, and what does it cost in
# registers" a check any developer and CI can run.
#
# Usage:
#   scripts/build_cuda_kernel.sh [--fetch] [--arch sm_70[,sm_80,...]]
#                               [--walks N] [--out DIR] [--cuda-path DIR]
#
# With a real CUDA toolkit installed, point --cuda-path at it (or set
# CUDA_PATH) and omit --fetch; nvcc is used when available, else clang.
set -eu

ARCHES="sm_70,sm_80,sm_89,sm_90"
WALKS=""
OUT="${OUT:-build-cuda-kernel}"
CUDA_PATH="${CUDA_PATH:-}"
FETCH=0
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

while [ $# -gt 0 ]; do
    case "$1" in
        --fetch) FETCH=1 ;;
        --arch) ARCHES="$2"; shift ;;
        --walks) WALKS="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        --cuda-path) CUDA_PATH="$2"; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

mkdir -p "$OUT"
OUT=$(CDPATH= cd -- "$OUT" && pwd)

if [ "$FETCH" = 1 ] && [ -z "$CUDA_PATH" ]; then
    CUDA_PATH="$OUT/cuda-toolkit"
    if [ ! -x "$CUDA_PATH/bin/ptxas" ]; then
        echo "== fetching the CUDA pieces we need from NVIDIA's pip wheels"
        WHEELS="$OUT/wheels"
        mkdir -p "$WHEELS" "$CUDA_PATH/include" "$CUDA_PATH/bin" "$CUDA_PATH/nvvm/libdevice"
        pip download -q --no-deps -d "$WHEELS" \
            nvidia-cuda-nvcc-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-cccl-cu12
        for w in "$WHEELS"/*.whl; do
            unzip -q -o "$w" -d "$WHEELS/x"
        done
        cp -r "$WHEELS"/x/nvidia/cuda_runtime/include/. "$CUDA_PATH/include/"
        cp -r "$WHEELS"/x/nvidia/cuda_nvcc/include/. "$CUDA_PATH/include/"
        cp -r "$WHEELS"/x/nvidia/cuda_cccl/include/. "$CUDA_PATH/include/"
        cp "$WHEELS"/x/nvidia/cuda_nvcc/nvvm/libdevice/libdevice.10.bc "$CUDA_PATH/nvvm/libdevice/"
        cp "$WHEELS"/x/nvidia/cuda_nvcc/bin/ptxas "$CUDA_PATH/bin/"
        chmod +x "$CUDA_PATH/bin/ptxas"
        # clang's CUDA wrapper includes a few headers that only ship with the
        # full toolkit and that our kernel never uses; stub them out.
        for h in cuda.h curand_mtgp32_kernel.h curand_kernel.h; do
            [ -f "$CUDA_PATH/include/$h" ] || \
                echo "/* stub: not used by the cryptanalysis kernel */" > "$CUDA_PATH/include/$h"
        done
    fi
fi

if [ -z "$CUDA_PATH" ]; then
    echo "error: no CUDA toolkit. Pass --fetch, or --cuda-path DIR, or set CUDA_PATH." >&2
    exit 1
fi
PTXAS="$CUDA_PATH/bin/ptxas"
[ -x "$PTXAS" ] || PTXAS=$(command -v ptxas || true)
[ -n "$PTXAS" ] || { echo "error: ptxas not found under $CUDA_PATH" >&2; exit 1; }

NVCC="$CUDA_PATH/bin/nvcc"
[ -x "$NVCC" ] || NVCC=$(command -v nvcc || true)

DEFS=""
[ -n "$WALKS" ] && DEFS="-DCA_GPU_W=$WALKS"

echo "== checking cuda/gpu_cuda.c compiles as C against the CUDA headers"
cc -fsyntax-only -std=gnu11 -D_GNU_SOURCE -DCA_BUILDING -Wall -Wextra -Werror \
    -I"$REPO/include" -I"$REPO/src" -I"$REPO/cuda" -I"$CUDA_PATH/include" \
    "$REPO/cuda/gpu_cuda.c"

echo "== compiling cuda/rho_kernel.cu (walks per thread: ${WALKS:-default})"
status=0
for ARCH in $(echo "$ARCHES" | tr ',' ' '); do
    PTX="$OUT/rho_kernel.$ARCH.ptx"
    CUBIN="$OUT/rho_kernel.$ARCH.cubin"
    if [ -n "$NVCC" ]; then
        "$NVCC" -ptx -arch="$ARCH" -O3 $DEFS \
            -I"$REPO/include" -I"$REPO/cuda" -I"$REPO/src" \
            -o "$PTX" "$REPO/cuda/rho_kernel.cu"
    else
        clang -x cuda --cuda-device-only --cuda-path="$CUDA_PATH" \
            --cuda-gpu-arch="$ARCH" -O3 $DEFS -Wno-unknown-cuda-version \
            -I"$REPO/include" -I"$REPO/cuda" -I"$REPO/src" \
            -S -o "$PTX" "$REPO/cuda/rho_kernel.cu"
    fi
    if ! info=$("$PTXAS" -arch="$ARCH" -v -o "$CUBIN" "$PTX" 2>&1); then
        echo "$ARCH: FAILED"
        echo "$info"
        status=1
        continue
    fi
    regs=$(echo "$info" | grep -o '[0-9][0-9]* registers' | head -1 | cut -d' ' -f1)
    stack=$(echo "$info" | grep -o '[0-9][0-9]* bytes stack frame' | head -1 | cut -d' ' -f1)
    spill=$(echo "$info" | grep -o '[0-9][0-9]* bytes spill stores' | head -1 | cut -d' ' -f1)
    printf '%-7s ok: %s registers, %s bytes local per thread, %s bytes spilled -> %s\n' \
        "$ARCH" "${regs:-?}" "${stack:-?}" "${spill:-0}" "$(basename "$CUBIN")"
    case "${spill:-0}" in
        0) ;;
        *) echo "  warning: the kernel is spilling registers" ;;
    esac
done
exit $status
