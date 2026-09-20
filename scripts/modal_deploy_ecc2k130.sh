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
export PATH="${HOME}/.local/bin:${PATH}"

need_modal() {
  command -v modal >/dev/null || pip install -q 'modal>=0.72'
  if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]]; then
    modal token set --id "$MODAL_TOKEN_ID" --secret "$MODAL_TOKEN_SECRET" --no-verify >/dev/null
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
}

run_in_ecc() {
  ( cd "$CRYPTO_DIR/ecc2k130" && ECC_GPU="$ECC_GPU" "$@" )
}

case "$CMD" in
  setup)
    need_modal
    ensure_crypto
    echo "ready: crypto=$CRYPTO_DIR gpu=$ECC_GPU"
    ;;
  deploy)
    need_modal
    ensure_crypto
    run_in_ecc modal deploy modal_app.py
    ;;
  bench)
    need_modal
    ensure_crypto
    # Use the one-block / tag-denom geometry via env knobs the Makefile target sets;
    # Modal rebuilds inside the image. Prefer packed bench matching RunPod.
    run_in_ecc modal run modal_app.py::bench --gpu "$ECC_GPU" --packed \
      --batch 16 --threads 512
    ;;
  search)
    need_modal
    ensure_crypto
    run_in_ecc modal run modal_app.py::search --gpu "$ECC_GPU" \
      --curve 131 --packed --hours "$ECC_HOURS" \
      --batch 16 --threads 512 --verify 0 --run-id 1
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
