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
set -euo pipefail

CMD="${1:-bench}"
CRYPTO_DIR="${CRYPTO_DIR:-$HOME/src/crypto}"
ECC_GPU="${ECC_GPU:-RTX-PRO-6000}"
ECC_HOURS="${ECC_HOURS:-1}"
ECC_FANOUT="${ECC_FANOUT:-4}"
ECC_RUN_ID="${ECC_RUN_ID:-4242}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

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
    run_in_ecc modal run modal_app.py::fanout --gpu "$ECC_GPU" \
      --curve 131 --packed --hours "$ECC_HOURS" --count "$ECC_FANOUT" \
      --batch 16 --threads 512 --verify 0
    ;;
  *)
    echo "usage: $0 [setup|deploy|bench|search|fanout]" >&2
    exit 2
    ;;
esac
