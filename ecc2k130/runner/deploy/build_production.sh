#!/usr/bin/env bash
# Build the validated ECC2K-130 production walk as a CUDA fat binary.
#
# The resulting executable contains native cubins for every supported SM in
# ECC_CUDA_ARCHES plus compute_120 PTX for forward-compatible drivers.  The
# runtime launcher selects the visible device and lets the CUDA driver load the
# matching cubin; no source checkout or nvcc is needed on the GPU host.
set -Eeuo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ARCHES=${1:-"80 86 89 90 100 120"}
flags=()
seen=" "

for sm in $ARCHES; do
    case "$sm" in
        80|86|89|90|100|120) ;;
        *)
            echo "unsupported CUDA architecture sm_${sm}; supported: sm_80 sm_86 sm_89 sm_90 sm_100 sm_120" >&2
            exit 2
            ;;
    esac
    case "$seen" in
        *" $sm "*) continue ;;
    esac
    seen="${seen}${sm} "
    flags+=("-gencode" "arch=compute_${sm},code=sm_${sm}")
done

if ((${#flags[@]} == 0)); then
    echo "ECC_CUDA_ARCHES must contain at least one supported architecture" >&2
    exit 2
fi

# Keep PTX for the newest supported architecture so a newer driver can JIT a
# future GPU.  Native cubins remain the normal path and CUDA_DISABLE_PTX_JIT=1
# can still be used by callers that require a no-JIT deployment.
flags+=("-gencode" "arch=compute_120,code=compute_120")
arch_flags="${flags[*]}"

cd "$ROOT"
make gpu-production "PRODUCTION_ARCH=${arch_flags}"
test -x ecc2k130
echo "built ECC2K-130 production fat binary for: ${ARCHES}" >&2
