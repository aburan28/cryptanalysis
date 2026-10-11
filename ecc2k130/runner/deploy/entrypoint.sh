#!/usr/bin/env bash
# Detect the first visible NVIDIA GPU and start the requested runner command.
# The image contains a CUDA fat binary; the CUDA driver loads the cubin that
# matches the detected SM.  ECC_DEVICE_INDEX is deliberately separate from
# ECC_GPU: the cloud supervisor uses ECC_GPU as its campaign GPU index.
set -Eeuo pipefail

ROOT=${ECC_IMAGE_ROOT:-/opt/ecc2k130}
DEVICE_INDEX=${ECC_DEVICE_INDEX:-}
if [[ -z "$DEVICE_INDEX" ]]; then
    # RunPod/EC2 use ECC_GPU for a numeric worker index. Modal uses the same
    # name for a provider GPU type at launch time, so ignore non-numeric values.
    case "${ECC_GPU:-}" in
        ''|*[!0-9]*) DEVICE_INDEX=0 ;;
        *) DEVICE_INDEX=$ECC_GPU ;;
    esac
fi
SUPPORTED_SMS=${ECC_SUPPORTED_SMS:-"80 86 89 90 100 120"}

if [[ "${ECC_SKIP_GPU_CHECK:-0}" == "1" ]]; then
    echo "ecc2k130: GPU detection skipped (ECC_SKIP_GPU_CHECK=1)" >&2
else
    compute_cap=${ECC_GPU_ARCH:-}
    gpu_name=${ECC_DEVICE_NAME:-}

    if [[ -z "$compute_cap" ]]; then
        if ! command -v nvidia-smi >/dev/null 2>&1; then
            echo "ecc2k130: nvidia-smi is unavailable; run with NVIDIA Container Toolkit" >&2
            echo "ecc2k130: or set ECC_GPU_ARCH (for example 8.0) for an explicit test override" >&2
            exit 2
        fi
        compute_cap=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits \
            -i "$DEVICE_INDEX" 2>/dev/null | sed -n '1p' | tr -d '[:space:]')
        gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader \
            -i "$DEVICE_INDEX" 2>/dev/null | sed -n '1p' | sed 's/[[:space:]]*$//')
    fi

    if [[ ! "$compute_cap" =~ ^[0-9]+\.[0-9]+$ ]]; then
        echo "ecc2k130: could not read a valid compute capability (got '${compute_cap:-empty}')" >&2
        exit 2
    fi

    major=${compute_cap%%.*}
    minor=${compute_cap#*.}
    # NVIDIA's early Blackwell drivers report 10.3 for parts that use the
    # sm_100 code path.  CUDA 13.3 does not expose an sm_103 target here.
    case "$major" in
        10) sm=100 ;;
        12) sm=120 ;;
        *) sm="${major}${minor}" ;;
    esac

    supported=0
    for candidate in $SUPPORTED_SMS; do
        if [[ "$candidate" == "$sm" ]]; then
            supported=1
            break
        fi
    done
    if ((supported == 0)); then
        echo "ecc2k130: unsupported GPU ${gpu_name:-device $DEVICE_INDEX} " \
             "(compute capability ${compute_cap}, resolved sm_${sm})" >&2
        echo "ecc2k130: supported architectures: ${SUPPORTED_SMS}" >&2
        exit 3
    fi

    export ECC_DETECTED_SM="$sm"
    export ECC_DEVICE_NAME="${gpu_name:-GPU ${DEVICE_INDEX}}"
    echo "ecc2k130: detected ${ECC_DEVICE_NAME} (compute capability ${compute_cap}, sm_${sm})" >&2
    echo "ecc2k130: CUDA will load the matching cubin from the production fat binary" >&2
fi

export ECC_CLIENT="${ECC_CLIENT:-$ROOT/ecc2k130}"
if [[ ! -x "$ECC_CLIENT" ]]; then
    echo "ecc2k130: ECC_CLIENT is not executable: $ECC_CLIENT" >&2
    exit 2
fi

if (($# == 0)); then
    set -- python3 "$ROOT/cloud.py" run --seconds "${ECC_RUN_SECONDS:-82800}"
fi
exec "$@"
