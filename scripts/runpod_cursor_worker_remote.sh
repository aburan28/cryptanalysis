#!/usr/bin/env bash
# Bootstrap a Cursor My Machines worker on this host (intended for a RunPod).
# Expected env:
#   CURSOR_API_KEY   personal user API key (required unless api-key file exists)
#   WORKER_NAME      display name in Cursor (default: hostname / RUNPOD_POD_NAME)
#   REPO_URL         git remote to serve (default: aburan28/cryptanalysis)
#   WORKER_DIR       checkout path (default: /root/cryptanalysis — /workspace is
#                    often a geesefs mount that rejects git chmod)
set -euo pipefail

WORKER_NAME="${WORKER_NAME:-${RUNPOD_POD_NAME:-$(hostname -s)}}"
REPO_URL="${REPO_URL:-https://github.com/aburan28/cryptanalysis.git}"
WORKER_DIR="${WORKER_DIR:-/root/cryptanalysis}"
DATA_DIR="${CURSOR_DATA_DIR:-/root/.cursor-worker}"
SESSION_NAME="${TMUX_SESSION:-cursor-worker}"
KEY_FILE="${DATA_DIR}/api-key"

export PATH="${HOME}/.local/bin:${PATH}"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

if [[ -n "${CURSOR_API_KEY:-}" ]]; then
  umask 077
  printf '%s' "$CURSOR_API_KEY" >"$KEY_FILE"
  chmod 600 "$KEY_FILE"
fi
if [[ ! -s "$KEY_FILE" ]]; then
  echo "CURSOR_API_KEY env or ${KEY_FILE} is required" >&2
  exit 1
fi

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

mkdir -p "$(dirname "$WORKER_DIR")"
if [[ -d "$WORKER_DIR/.git" ]]; then
  git -C "$WORKER_DIR" -c core.filemode=false fetch --prune origin
  git -C "$WORKER_DIR" -c core.filemode=false checkout main
  git -C "$WORKER_DIR" -c core.filemode=false pull --ff-only origin main || true
else
  git -c core.filemode=false clone --depth 1 "$REPO_URL" "$WORKER_DIR"
fi

# Launcher keeps the API key out of process argv / tmux command lines.
LAUNCHER="${DATA_DIR}/start-worker.sh"
cat >"$LAUNCHER" <<SH
#!/usr/bin/env bash
set -euo pipefail
export PATH="\${HOME}/.local/bin:\${PATH}"
export CURSOR_API_KEY="\$(tr -d '\\n' <$(printf '%q' "$KEY_FILE"))"
export CURSOR_DATA_DIR=$(printf '%q' "$DATA_DIR")
exec agent worker \\
  --name $(printf '%q' "$WORKER_NAME") \\
  --worker-dir $(printf '%q' "$WORKER_DIR") \\
  --data-dir $(printf '%q' "$DATA_DIR") \\
  --idle-release-timeout 0 \\
  --label provider=runpod \\
  --label role=cryptanalysis \\
  --label pod=$(printf '%q' "$WORKER_NAME") \\
  start --verbose
SH
chmod 700 "$LAUNCHER"

if tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "=$SESSION_NAME"
fi

tmux new-session -d -s "$SESSION_NAME" -c "$WORKER_DIR" -- "$LAUNCHER"

sleep 3
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
