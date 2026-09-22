#!/usr/bin/env bash
# Deploy / run the ECC2K-130 20 B/s client on Modal.
#
# Requires a checkout of aburan28/crypto (main includes #507) and Modal tokens:
#   export MODAL_TOKEN_ID=...
#   export MODAL_TOKEN_SECRET=...
#   # or: modal token set --id … --secret …
#
# Usage:
#   ./scripts/modal_deploy_ecc2k130.sh setup     # clone/update crypto + modal auth check
#   ./scripts/modal_deploy_ecc2k130.sh deploy    # modal deploy the ecc2k130 app
#   ./scripts/modal_deploy_ecc2k130.sh bench     # packed throughput on RTX-PRO-6000
#   ./scripts/modal_deploy_ecc2k130.sh search    # curve-131 packed search (hours=ECC_HOURS)
#   ./scripts/modal_deploy_ecc2k130.sh fanout    # N parallel searchers
#   ./scripts/modal_deploy_ecc2k130.sh long      # 24h × ECC_FANOUT GPUs
#   ./scripts/modal_deploy_ecc2k130.sh sync      # Modal volume → S3 (status page)
#   ./scripts/modal_deploy_ecc2k130.sh sync-loop # sync every SYNC_INTERVAL seconds
#
# Prefer the unified entrypoint: ./scripts/cloud_launch.sh modal <cmd>
set -euo pipefail

CMD="${1:-bench}"
CRYPTO_DIR="${CRYPTO_DIR:-$HOME/src/crypto}"
ECC_GPU="${ECC_GPU:-RTX-PRO-6000}"
ECC_HOURS="${ECC_HOURS:-24}"
ECC_FANOUT="${ECC_FANOUT:-4}"
ECC_RUN_ID="${ECC_RUN_ID:-4242}"
SYNC_INTERVAL="${SYNC_INTERVAL:-120}"
SYNC_RUN_IDS="${SYNC_RUN_IDS:-$ECC_RUN_ID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

# Cursor / cloud-agent AWS secret aliases
if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -n "${Awskeyid:-}" ]]; then
  export AWS_ACCESS_KEY_ID="$Awskeyid"
fi
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${Awssecret:-}" ]]; then
  export AWS_SECRET_ACCESS_KEY="$Awssecret"
fi
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# ONE-BLOCK-GEOMETRY.md / make gpu-rtx-pro6000-20b — must match the RunPod binary.
export ECC_CUDA_VERSION="${ECC_CUDA_VERSION:-13.3.1}"
export ECC_PACKED_SINGLE_PRODUCT=1
export ECC_PACKED_CACHE_DENOM=1
export ECC_PACKED_BY_VALUE=1
export ECC_PACKED_PERM_SIGMA=3
export ECC_PACKED_POLY_CHAIN=1
export ECC_PACKED_UNROLL_INV=1
export ECC_PACKED_PAIR_PRODUCTS=1
export ECC_PACKED_POLY_STATE=1
export ECC_PACKED_DIRECT_REDUCE=1
export ECC_PACKED_GENERATED_PRODUCT=1
export ECC_PACKED_CLMAD=1
export ECC_PACKED_STATE_TILE=256
export ECC_PACKED_WEIGHTED_PREFIX=2
export ECC_PACKED_COMPACT_STATE=1
export ECC_PACKED_SHARED_SIGMA=1
export ECC_WALK_TABLE=1
export ECC_TABLE_PIVOT_BYTES=1
export ECC_TABLE_TAG_DENOM=1
export ECC_TABLE_PIPE_SELECT=1
export ECC_PACKED_CHAIN_FIRST=1
export ECC_PACKED_INLINE_POLY=3
export ECC_PACKED_PAIR_ILP=1
export ECC_PACKED_L2_PERSIST=1
export ECC_PACKED_ALU_SQUARE=1
export ECC_PACKED_FROM_REDUCED=1
export ECC_UNROLL_SLOTS=1
export ECC_GPU

need_modal() {
  command -v modal >/dev/null || pip install -q 'modal>=0.72'
  if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]]; then
    modal token set --token-id "$MODAL_TOKEN_ID" --token-secret "$MODAL_TOKEN_SECRET" --no-verify >/dev/null
  fi
  modal profile current >/dev/null 2>&1 || {
    echo "Modal is not authenticated." >&2
    echo "Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (https://modal.com/settings/tokens)." >&2
    exit 1
  }
}

ensure_crypto() {
  if [[ ! -d "$CRYPTO_DIR/.git" ]]; then
    mkdir -p "$(dirname "$CRYPTO_DIR")"
    git clone --depth 1 https://github.com/aburan28/crypto.git "$CRYPTO_DIR"
  fi
  git -C "$CRYPTO_DIR" fetch --depth 1 origin main
  git -C "$CRYPTO_DIR" checkout -B ecc2k-deploy origin/main
  git -C "$CRYPTO_DIR" log -1 --oneline
  # Sanity: 20 B/s target must exist (#507).
  grep -q 'gpu-rtx-pro6000-20b' "$CRYPTO_DIR/ecc2k130/Makefile"
  # Stock modal_app.py cannot bake the 20 B/s knobs; overlay locally.
  python3 "$SCRIPT_DIR/patch_modal_app_20b.py" "$CRYPTO_DIR/ecc2k130/modal_app.py"
}

run_in_ecc() {
  ( cd "$CRYPTO_DIR/ecc2k130" && "$@" )
}

case "$CMD" in
  setup)
    need_modal
    ensure_crypto
    echo "ready: crypto=$CRYPTO_DIR gpu=$ECC_GPU geometry=20b"
    ;;
  deploy)
    need_modal
    ensure_crypto
    run_in_ecc modal deploy modal_app.py
    ;;
  bench)
    need_modal
    ensure_crypto
    run_in_ecc modal run modal_app.py::bench --gpu "$ECC_GPU" --packed \
      --batch 16 --threads 512 --min-blocks 1 \
      --steps 1024 --launches 32 --repeats 3
    ;;
  search)
    need_modal
    ensure_crypto
    # search has no --min-blocks CLI; overlay forces MINBLOCKS=1 via TABLE_TAG_DENOM.
    # Use a dedicated run-id so we do not resume an incompatible volume checkpoint.
    run_in_ecc modal run modal_app.py::search --gpu "$ECC_GPU" \
      --curve 131 --packed --hours "$ECC_HOURS" \
      --batch 16 --threads 512 --verify 0 --run-id "$ECC_RUN_ID"
    ;;
  fanout)
    need_modal
    ensure_crypto
    # --detach keeps workers alive if the local client disconnects (watchdog-
    # friendly). base_run_id avoids stale volume run-id 1.
    run_in_ecc modal run --detach modal_app.py::fanout --gpu "$ECC_GPU" \
      --curve 131 --packed --hours "$ECC_HOURS" --count "$ECC_FANOUT" \
      --batch 16 --threads 512 --verify 0 --base-run-id "$ECC_RUN_ID"
    ;;
  long)
    # Convenience: 24h x 4-GPU fanout on the 20 B/s geometry.
    need_modal
    ensure_crypto
    run_in_ecc modal run --detach modal_app.py::fanout --gpu "$ECC_GPU" \
      --curve 131 --packed --hours "${ECC_HOURS:-24}" --count "${ECC_FANOUT:-4}" \
      --batch 16 --threads 512 --verify 0 --base-run-id "$ECC_RUN_ID"
    ;;
  sync|sync-loop)
    need_modal
    ensure_crypto
    python3 -c 'import boto3' 2>/dev/null || pip install -q boto3
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
      echo "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY required to publish Modal workers to the status page." >&2
      exit 1
    fi
    # Expand a single ECC_RUN_ID into fanout range so sync matches long/fanout.
    if [[ "$SYNC_RUN_IDS" == "$ECC_RUN_ID" && "${ECC_FANOUT:-1}" -gt 1 ]]; then
      ids=()
      for ((i = 0; i < ECC_FANOUT; i++)); do ids+=("$((ECC_RUN_ID + i))"); done
      IFS=,; SYNC_RUN_IDS="${ids[*]}"; unset IFS
    fi
    bucket_args=()
    if [[ -n "${ECC_BUCKET:-}" ]]; then
      bucket_args=(--bucket "$ECC_BUCKET")
    fi
    if [[ "$CMD" == sync ]]; then
      run_in_ecc python3 modal_sync.py --curve 131 --run-ids "$SYNC_RUN_IDS" \
        --all-runs "${bucket_args[@]}"
    else
      echo "sync-loop every ${SYNC_INTERVAL}s for runs ${SYNC_RUN_IDS} (+ volume discovery)"
      run_in_ecc python3 modal_sync.py --curve 131 --run-ids "$SYNC_RUN_IDS" \
        --all-runs --watch "$SYNC_INTERVAL" "${bucket_args[@]}"
    fi
    ;;
  *)
    echo "usage: $0 [setup|deploy|bench|search|fanout|long|sync|sync-loop]" >&2
    exit 2
    ;;
esac
