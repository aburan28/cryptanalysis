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
#                               [--host-gcc DIR]
#
# With a real CUDA toolkit installed, point --cuda-path at it (or set
# CUDA_PATH) and omit --fetch; nvcc is used when available, else clang.
set -eu

ARCHES="sm_70,sm_80,sm_89,sm_90"
WALKS=""
OUT="${OUT:-build-cuda-kernel}"
CUDA_PATH="${CUDA_PATH:-}"
HOST_GCC="${HOST_GCC:-}"
FETCH=0
REPO=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

while [ $# -gt 0 ]; do
    case "$1" in
        --fetch) FETCH=1 ;;
        --arch) ARCHES="$2"; shift ;;
        --walks) WALKS="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        --cuda-path) CUDA_PATH="$2"; shift ;;
        --host-gcc) HOST_GCC="$2"; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

mkdir -p "$OUT"
OUT=$(CDPATH='' cd -- "$OUT" && pwd)

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

# Compile the kernel to PTX with clang.  $1 = arch, $2 = output, $3 = extra
# flags (may be empty).
clang_ptx() {
    # shellcheck disable=SC2086  # $DEFS and $3 are deliberately word-split
    clang -x cuda --cuda-device-only --cuda-path="$CUDA_PATH" \
        --cuda-gpu-arch="$1" -O3 $DEFS -Wno-unknown-cuda-version $3 \
        -I"$REPO/include" -I"$REPO/cuda" -I"$REPO/src" \
        -S -o "$2" "$REPO/cuda/rho_kernel.cu" 2>&1
}

# clang compiling CUDA force-includes its own wrapper header, which pulls in
# libstdc++'s <cmath> and hence <limits>.  From GCC 14 on that declares
# numeric_limits<__float128>, and __float128 does not exist on the NVPTX
# target, so the compile fails with errors that have nothing to do with this
# kernel.  Pointing clang at an older GCC's headers avoids it, so when the
# default host GCC fails we retry against each installed one, oldest first.
# (--host-gcc DIR picks one explicitly; nvcc is unaffected by all of this.)
pick_host_gcc() {
    arch="$1"
    if [ -n "$HOST_GCC" ]; then
        echo "--gcc-install-dir=$HOST_GCC"
        return 0
    fi
    if clang_ptx "$arch" /dev/null "" >/dev/null 2>&1; then
        echo ""
        return 0
    fi
    # Oldest GCC first: newer libstdc++ headers are the ones that declare
    # numeric_limits<__float128>, which NVPTX has no type for.
    while IFS= read -r d; do
        [ -d "$d" ] || continue
        if clang_ptx "$arch" /dev/null "--gcc-install-dir=$d" >/dev/null 2>&1; then
            echo "--gcc-install-dir=$d"
            return 0
        fi
    done <<EOF
$(find /usr/lib/gcc -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort -V)
EOF
    echo ""
    return 1
}

echo "== checking cuda/gpu_cuda.c compiles as C against the CUDA headers"
cc -fsyntax-only -std=gnu11 -D_GNU_SOURCE -DCA_BUILDING -Wall -Wextra -Werror \
    -I"$REPO/include" -I"$REPO/src" -I"$REPO/cuda" -I"$CUDA_PATH/include" \
    "$REPO/cuda/gpu_cuda.c"

echo "== compiling cuda/rho_kernel.cu (walks per thread: ${WALKS:-default})"
status=0
GCC_FLAG=""
GCC_FLAG_SET=0
for ARCH in $(echo "$ARCHES" | tr ',' ' '); do
    PTX="$OUT/rho_kernel.$ARCH.ptx"
    CUBIN="$OUT/rho_kernel.$ARCH.cubin"
    if [ -n "$NVCC" ]; then
        # shellcheck disable=SC2086
        "$NVCC" -ptx -arch="$ARCH" -O3 $DEFS \
            -I"$REPO/include" -I"$REPO/cuda" -I"$REPO/src" \
            -o "$PTX" "$REPO/cuda/rho_kernel.cu"
    else
        if [ "$GCC_FLAG_SET" = 0 ]; then
            GCC_FLAG=$(pick_host_gcc "$ARCH") || true
            GCC_FLAG_SET=1
            case "$GCC_FLAG" in
                --gcc-install-dir=*) echo "   (host GCC headers: ${GCC_FLAG#--gcc-install-dir=})" ;;
            esac
        fi
        if ! out=$(clang_ptx "$ARCH" "$PTX" "$GCC_FLAG"); then
            echo "$ARCH: clang failed"
            echo "$out" | head -20
            status=1
            continue
        fi
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
