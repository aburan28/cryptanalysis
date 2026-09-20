#!/usr/bin/env bash
# Bootstrap a Cursor My Machines worker on this host (intended for a RunPod).
# Expected env:
#   CURSOR_API_KEY   personal user API key (required)
#   WORKER_NAME      display name in Cursor (default: hostname)
#   REPO_URL         git remote to serve (default: aburan28/cryptanalysis)
#   WORKER_DIR       checkout path (default: /workspace/cryptanalysis)
set -euo pipefail

: "${CURSOR_API_KEY:?CURSOR_API_KEY is required}"

WORKER_NAME="${WORKER_NAME:-${RUNPOD_POD_NAME:-$(hostname -s)}}"
REPO_URL="${REPO_URL:-https://github.com/aburan28/cryptanalysis.git}"
WORKER_DIR="${WORKER_DIR:-/workspace/cryptanalysis}"
DATA_DIR="${CURSOR_DATA_DIR:-/workspace/.cursor-worker}"
SESSION_NAME="${TMUX_SESSION:-cursor-worker}"

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v agent >/dev/null 2>&1; then
  curl -fsS https://cursor.com/install | bash
  export PATH="${HOME}/.local/bin:${PATH}"
fi

command -v agent >/dev/null
command -v git >/dev/null
command -v tmux >/dev/null || {
  if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq tmux git curl ca-certificates
  else
    echo "tmux is required but not installed" >&2
    exit 1
  fi
}

mkdir -p "$(dirname "$WORKER_DIR")" "$DATA_DIR"
if [[ -d "$WORKER_DIR/.git" ]]; then
  git -C "$WORKER_DIR" fetch --prune origin
  git -C "$WORKER_DIR" checkout main
  git -C "$WORKER_DIR" pull --ff-only origin main || true
else
  git clone --depth 1 "$REPO_URL" "$WORKER_DIR"
fi

# Stop an older worker in this tmux session if present.
if tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "=$SESSION_NAME"
fi

# Long-lived personal worker: disable idle release so the GPU pod stays claimed.
# Labels help route calculation jobs to this machine. Auth via CURSOR_API_KEY env.
tmux new-session -d -s "$SESSION_NAME" -c "$WORKER_DIR" -- \
  env PATH="$PATH" CURSOR_API_KEY="$CURSOR_API_KEY" CURSOR_DATA_DIR="$DATA_DIR" \
  agent worker \
    --name "$WORKER_NAME" \
    --worker-dir "$WORKER_DIR" \
    --data-dir "$DATA_DIR" \
    --idle-release-timeout 0 \
    --label "provider=runpod" \
    --label "role=cryptanalysis" \
    --label "pod=${WORKER_NAME}" \
    start \
    --verbose

sleep 2
if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
  echo "worker tmux session failed to stay up" >&2
  exit 1
fi

echo "cursor worker started"
echo "  name:    $WORKER_NAME"
echo "  dir:     $WORKER_DIR"
echo "  tmux:    $SESSION_NAME"
echo "  version: $(agent --version 2>/dev/null || true)"
echo "attach logs: tmux attach -t $SESSION_NAME"
