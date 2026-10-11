#!/usr/bin/env bash
# One entrypoint for cloud ECC2K-130 / cryptanalysis GPU launches.
#
#   ./scripts/cloud_launch.sh doctor          # what is missing?
#   ./scripts/cloud_launch.sh modal long      # 24h × 4 GPU Modal fanout (20 B/s)
#   ./scripts/cloud_launch.sh modal bench
#   ./scripts/cloud_launch.sh modal sync      # volume → S3 (status page)
#   ./scripts/cloud_launch.sh runpod start|status|stop
#   ./scripts/cloud_launch.sh sync ensure|status|stop   # Modal→S3 durable syncer
#   ./scripts/cloud_launch.sh fanout start|status|stop   # 8× on marginal_chocolate_ostrich
#   ./scripts/cloud_launch.sh ingest start|status|stop   # MiG pod "ingest" → Postgres/status
#   ./scripts/cloud_launch.sh all             # doctor + ingest + runpod + modal long
#
# Credentials (env or already-configured CLIs):
#   MODAL_TOKEN_ID + MODAL_TOKEN_SECRET   https://modal.com/settings/tokens
#   RUNPOD_API_KEY                       https://www.runpod.io/console/user/settings
#   AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY   (Modal sync + ingest MiG pod)
#   ECC_BUCKET                           (optional; default ecc2k130-<account>)
#
# Docs: docs/CLOUD_LAUNCH.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

# Accept Awskeyid/Awssecret aliases used in some Cursor environments.
if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -n "${Awskeyid:-}" ]]; then
  export AWS_ACCESS_KEY_ID="$Awskeyid"
fi
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${Awssecret:-}" ]]; then
  export AWS_SECRET_ACCESS_KEY="$Awssecret"
fi
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

ok() { printf '  ✓ %s\n' "$*"; }
bad() { printf '  ✗ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
hint() { printf '    → %s\n' "$*"; }

ensure_modal_cli() {
  if command -v modal >/dev/null 2>&1; then
    return 0
  fi
  pip install -q 'modal>=0.72' || return 1
  command -v modal >/dev/null 2>&1
}

modal_ready() {
  ensure_modal_cli || return 1
  if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]]; then
    modal token set --token-id "$MODAL_TOKEN_ID" --token-secret "$MODAL_TOKEN_SECRET" \
      --no-verify >/dev/null 2>&1 || true
  fi
  modal profile current >/dev/null 2>&1
}

runpod_ready() {
  [[ -n "${RUNPOD_API_KEY:-}" ]] || return 1
  command -v runpodctl >/dev/null 2>&1 || return 1
  [[ -f "${SSH_KEY:-$HOME/.ssh/id_ed25519}" ]] || return 1
  return 0
}

doctor() {
  local modal_ok=0 runpod_ok=0
  echo "cloud_launch doctor"
  echo "──────────────────"

  if ensure_modal_cli; then
    if modal_ready; then
      ok "Modal CLI authenticated"
      modal_ok=1
    else
      bad "Modal CLI present but not authenticated"
      hint "export MODAL_TOKEN_ID=… MODAL_TOKEN_SECRET=…  (https://modal.com/settings/tokens)"
    fi
  else
    bad "modal CLI missing (pip install 'modal>=0.72' failed or not on PATH)"
    hint "pip install 'modal>=0.72' then set MODAL_TOKEN_ID / MODAL_TOKEN_SECRET"
  fi

  if [[ -n "${RUNPOD_API_KEY:-}" ]]; then
    if ! command -v runpodctl >/dev/null 2>&1; then
      bad "RUNPOD_API_KEY set but runpodctl missing"
      hint "Install runpodctl: https://docs.runpod.io/runpodctl"
    elif [[ ! -f "${SSH_KEY:-$HOME/.ssh/id_ed25519}" ]]; then
      bad "RUNPOD_API_KEY set but no SSH key at ${SSH_KEY:-$HOME/.ssh/id_ed25519}"
      hint "ssh-keygen -t ed25519  (or set SSH_KEY=…)"
    else
      ok "RunPod API key + runpodctl + SSH key"
      runpod_ok=1
    fi
  else
    warn "RUNPOD_API_KEY not set (RunPod launches disabled)"
    hint "export RUNPOD_API_KEY=… from the RunPod console"
  fi

  if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    if python3 -c 'import boto3' 2>/dev/null; then
      ok "AWS credentials + boto3 (Modal→S3 sync + ingest MiG)"
    else
      warn "AWS credentials set but boto3 missing"
      hint "pip install boto3"
    fi
  else
    warn "AWS credentials not set (Modal sync + ingest MiG disabled)"
    hint "export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… for sync/ingest"
  fi

  if [[ "$runpod_ok" -eq 1 ]]; then
    ok "ingest MiG path available (pod name ${INGEST_POD_NAME:-ingest})"
  fi

  echo
  if [[ "$modal_ok" -eq 1 || "$runpod_ok" -eq 1 ]]; then
    echo "Ready (at least one backend)."
    [[ "$modal_ok" -eq 1 ]] && echo "  $0 modal long          # one-click Modal fanout"
    [[ "$runpod_ok" -eq 1 ]] && echo "  $0 runpod status       # GPU campaign pod"
    [[ "$runpod_ok" -eq 1 ]] && echo "  $0 ingest start        # MiG ingest → Postgres/status"
    [[ "$modal_ok" -eq 1 ]] && echo "  $0 modal sync-loop     # optional Modal volume → S3"
    return 0
  fi
  echo "No backend ready. Fix the ✗ items above, then re-run: $0 doctor"
  echo "Docs: $ROOT/docs/CLOUD_LAUNCH.md"
  return 1
}

modal_cmd() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    ""|help|-h|--help)
      echo "usage: $0 modal [doctor|setup|deploy|bench|search|fanout|long|sync|sync-loop]" >&2
      exit 2
      ;;
    doctor)
      doctor
      ;;
    *)
      exec "$SCRIPT_DIR/modal_deploy_ecc2k130.sh" "$sub" "$@"
      ;;
  esac
}

runpod_cmd() {
  local sub="${1:-status}"
  shift || true
  exec "$SCRIPT_DIR/runpod_deploy_ecc2k130.sh" "$sub" "$@"
}

fanout_cmd() {
  local sub="${1:-status}"
  shift || true
  exec "$SCRIPT_DIR/runpod_fanout_ecc2k130.sh" "$sub" "$@"
}

sync_cmd() {
  local sub="${1:-ensure}"
  shift || true
  case "$sub" in
    ensure|start|status|stop|restart)
      exec "$SCRIPT_DIR/ensure_modal_sync.sh" "$sub" "$@"
      ;;
    runpod)
      # POD_NAME / CAMP_ROOT / WORKERS via env
      exec "$SCRIPT_DIR/runpod_s3_sync_ecc2k130.sh" "${1:-start}"
      ;;
    *)
      echo "usage: $0 sync [ensure|status|stop|restart|runpod]" >&2
      exit 2
      ;;
  esac
}

ingest_cmd() {
  local sub="${1:-status}"
  shift || true
  exec "$SCRIPT_DIR/runpod_ingest_ecc2k130.sh" "$sub" "$@"
}

all_cmd() {
  doctor || true
  echo
  echo "== Ingest MiG status =="
  if runpod_ready && [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    "$SCRIPT_DIR/runpod_ingest_ecc2k130.sh" status || true
  else
    echo "(skipped — need RUNPOD_API_KEY + SSH + AWS_* for ingest)"
  fi
  echo
  echo "== RunPod GPU status =="
  if runpod_ready; then
    "$SCRIPT_DIR/runpod_deploy_ecc2k130.sh" status || true
  else
    echo "(skipped — RunPod not configured)"
  fi
  echo
  echo "== Modal long fanout (24h × ${ECC_FANOUT:-4} GPUs) =="
  if modal_ready; then
    "$SCRIPT_DIR/modal_deploy_ecc2k130.sh" long
  else
    echo "(skipped — Modal not configured)"
    exit 1
  fi
}

usage() {
  cat <<EOF
cloud_launch — one entrypoint for Modal / RunPod ECC2K-130 launches

Usage:
  $0 doctor
  $0 modal <setup|deploy|bench|search|fanout|long|sync|sync-loop>
  $0 runpod <start|status|stop>          # GPU campaign (solar_ivory_canidae)
  $0 fanout <start|status|stop>          # N workers on marginal_chocolate_ostrich (8 MIG)
  $0 sync <ensure|status|stop|restart>   # Modal volume → S3 (must stay up)
  $0 sync runpod                         # RunPod dps.bin → S3 (POD_NAME/CAMP_ROOT)
  $0 ingest <start|status|stop>          # MiG pod "ingest" → Postgres/status.json
  $0 all                                 # doctor, ingest+runpod status, modal long

Make aliases:
  make cloud-doctor
  make modal-long
  make modal-sync-ensure
  make fanout-start
  make ingest-start
  make modal-sync

GitHub one-click:
  Actions → "Cloud ECC2K-130" → Run workflow
  (needs repo secrets MODAL_TOKEN_ID, MODAL_TOKEN_SECRET; optional RUNPOD_API_KEY, AWS_*)

Docs: docs/CLOUD_LAUNCH.md

Env knobs: ECC_HOURS (default 24), ECC_FANOUT (4), ECC_RUN_ID (4242),
           ECC_GPU (RTX-PRO-6000), POD_NAME (solar_ivory_canidae),
           INGEST_POD_NAME (ingest), WORKERS (8), BASE_RUN_ID (5000), ECC_BUCKET
EOF
}

CMD="${1:-}"
shift || true
case "$CMD" in
  doctor) doctor ;;
  modal) modal_cmd "$@" ;;
  runpod) runpod_cmd "$@" ;;
  fanout) fanout_cmd "$@" ;;
  sync) sync_cmd "$@" ;;
  ingest) ingest_cmd "$@" ;;
  all) all_cmd ;;
  help|-h|--help|"") usage ;;
  *)
    echo "unknown command: $CMD" >&2
    usage >&2
    exit 2
    ;;
esac
