#!/usr/bin/env bash
# Keep Modal volume → S3 sync running in a durable local tmux session.
#
# Modal workers write DPs to a Modal volume; the status page / ingest only see
# S3. This wrapper starts (or restarts) modal_sync.py --watch in tmux so the
# syncer survives shell exits.
#
# Required: MODAL_TOKEN_ID/SECRET (or modal profile), AWS_ACCESS_KEY_ID/SECRET
# Optional: ECC_BUCKET, ECC_RUN_ID, ECC_FANOUT, SYNC_INTERVAL, CRYPTO_DIR
#
# Usage:
#   ./scripts/ensure_modal_sync.sh          # start if down
#   ./scripts/ensure_modal_sync.sh status
#   ./scripts/ensure_modal_sync.sh stop
#   ./scripts/ensure_modal_sync.sh restart
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -n "${Awskeyid:-}" ]]; then
  export AWS_ACCESS_KEY_ID="$Awskeyid"
fi
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${Awssecret:-}" ]]; then
  export AWS_SECRET_ACCESS_KEY="$Awssecret"
fi
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

CRYPTO_DIR="${CRYPTO_DIR:-$HOME/src/crypto}"
ECC_RUN_ID="${ECC_RUN_ID:-4242}"
ECC_FANOUT="${ECC_FANOUT:-4}"
SYNC_INTERVAL="${SYNC_INTERVAL:-120}"
ECC_BUCKET="${ECC_BUCKET:-ecc2k130-590183823895}"
TMUX_SESSION="${TMUX_SESSION:-ecc2k130-modal-sync}"
LOG="${LOG:-/opt/cursor/artifacts/modal-sync-watch.log}"
STATE_DIR="${ECC_MODAL_SYNC_STATE:-/opt/cursor/artifacts/ecc2k130-modal-sync-state}"
CMD="${1:-start}"

ids=()
for ((i = 0; i < ECC_FANOUT; i++)); do ids+=("$((ECC_RUN_ID + i))"); done
IFS=,; SYNC_RUN_IDS="${ids[*]}"; unset IFS

need_creds() {
  [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]] \
    || { echo "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY required" >&2; exit 1; }
  if [[ -n "${MODAL_TOKEN_ID:-}" && -n "${MODAL_TOKEN_SECRET:-}" ]]; then
    modal token set --token-id "$MODAL_TOKEN_ID" --token-secret "$MODAL_TOKEN_SECRET" \
      --no-verify >/dev/null 2>&1 || true
  fi
  modal profile current >/dev/null 2>&1 \
    || { echo "Modal not authenticated" >&2; exit 1; }
  [[ -f "$CRYPTO_DIR/ecc2k130/modal_sync.py" ]] \
    || { echo "missing $CRYPTO_DIR/ecc2k130/modal_sync.py — run modal setup" >&2; exit 1; }
  python3 -c 'import boto3' 2>/dev/null || pip install -q boto3
  command -v tmux >/dev/null || { echo "tmux required" >&2; exit 1; }
}

is_up() {
  tmux has-session -t "=$TMUX_SESSION" 2>/dev/null
}

stop_loose() {
  # Stop any non-tmux modal_sync watchers so we do not double-upload.
  pkill -f 'python3 modal_sync.py .*--watch' 2>/dev/null || true
}

start_sync() {
  need_creds
  mkdir -p "$(dirname "$LOG")" "$STATE_DIR"
  stop_loose
  tmux kill-session -t "=$TMUX_SESSION" 2>/dev/null || true
  sleep 1

  # Export into the tmux environment.
  tmux new-session -d -s "$TMUX_SESSION" -c "$CRYPTO_DIR/ecc2k130" -- \
    env \
      PATH="$PATH" \
      AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
      ECC_BUCKET="$ECC_BUCKET" \
      ECC_MODAL_SYNC_STATE="$STATE_DIR" \
      SYNC_RUN_IDS="$SYNC_RUN_IDS" \
      SYNC_INTERVAL="$SYNC_INTERVAL" \
      LOG="$LOG" \
      bash -c '
        set -uo pipefail
        echo "modal-sync start $(date -u +%Y-%m-%dT%H:%M:%SZ) runs=$SYNC_RUN_IDS interval=$SYNC_INTERVAL" | tee -a "$LOG"
        while true; do
          python3 modal_sync.py --curve 131 --run-ids "$SYNC_RUN_IDS" --all-runs \
            --bucket "$ECC_BUCKET" --watch "$SYNC_INTERVAL" \
            --state-dir "$ECC_MODAL_SYNC_STATE" \
            2>&1 | tee -a "$LOG"
          echo "modal-sync exited $? at $(date -u +%Y-%m-%dT%H:%M:%SZ); restarting in 5s" | tee -a "$LOG"
          sleep 5
        done
      '
  sleep 3
  if is_up; then
    echo "tmux=$TMUX_SESSION up (runs $SYNC_RUN_IDS → s3://$ECC_BUCKET/dp/)"
    tmux capture-pane -t "$TMUX_SESSION" -p -S -15 | tail -12
  else
    echo "failed to start $TMUX_SESSION" >&2
    exit 1
  fi
}

case "$CMD" in
  start|ensure)
    if is_up; then
      echo "already running: tmux=$TMUX_SESSION"
      tmux capture-pane -t "$TMUX_SESSION" -p -S -10 | tail -8
      exit 0
    fi
    start_sync
    ;;
  restart)
    start_sync
    ;;
  stop)
    tmux kill-session -t "=$TMUX_SESSION" 2>/dev/null || true
    stop_loose
    echo stopped
    ;;
  status)
    if is_up; then
      echo "tmux=$TMUX_SESSION up"
      tmux capture-pane -t "$TMUX_SESSION" -p -S -20 | tail -15
    else
      echo "tmux=$TMUX_SESSION down"
      if pgrep -af 'modal_sync.py' >/dev/null 2>&1; then
        echo "loose modal_sync process still alive:"
        pgrep -af 'modal_sync.py' || true
      fi
      exit 1
    fi
    if [[ -f "$LOG" ]]; then
      echo "--- log tail ($LOG) ---"
      tail -8 "$LOG"
    fi
    ;;
  *)
    echo "usage: $0 [start|ensure|status|stop|restart]" >&2
    exit 2
    ;;
esac
