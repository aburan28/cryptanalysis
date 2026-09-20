#!/usr/bin/env bash
# Find a RunPod by name, SSH in, and start a Cursor My Machines worker there.
#
# Required env:
#   RUNPOD_API_KEY     RunPod API key
#   CURSOR_API_KEY     personal Cursor user API key (Dashboard → API Keys)
#
# Optional env:
#   POD_NAME           RunPod name (default: solar_ivory_canidae)
#   WORKER_NAME        Cursor worker display name (default: POD_NAME)
#   REPO_URL           git remote to clone on the pod
#   WORKER_DIR         checkout path on the pod
#   SSH_KEY            private key path (default: ~/.ssh/id_ed25519)
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"
: "${CURSOR_API_KEY:?CURSOR_API_KEY is required (personal user key for My Machines)}"

POD_NAME="${POD_NAME:-solar_ivory_canidae}"
WORKER_NAME="${WORKER_NAME:-$POD_NAME}"
REPO_URL="${REPO_URL:-https://github.com/aburan28/cryptanalysis.git}"
WORKER_DIR="${WORKER_DIR:-/root/cryptanalysis}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_SCRIPT="${SCRIPT_DIR}/runpod_cursor_worker_remote.sh"

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v runpodctl >/dev/null 2>&1; then
  echo "installing runpodctl into ~/.local/bin ..."
  OS=$(uname -s)
  case "$OS" in
    Linux) OS=linux ;;
    Darwin) OS=darwin ;;
    *) echo "unsupported os: $OS" >&2; exit 1 ;;
  esac
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) ARCH=amd64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
  esac
  ASSET="runpodctl-${OS}-${ARCH}"
  VER="$(curl -fsSL https://api.github.com/repos/runpod/runpodctl/releases/latest | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"])')"
  mkdir -p "${HOME}/.local/bin"
  curl -fsSL -o "${HOME}/.local/bin/runpodctl" \
    "https://github.com/runpod/runpodctl/releases/download/${VER}/${ASSET}"
  chmod +x "${HOME}/.local/bin/runpodctl"
fi

if [[ ! -f "$SSH_KEY" ]]; then
  mkdir -p "$(dirname "$SSH_KEY")"
  ssh-keygen -t ed25519 -N "" -f "$SSH_KEY" -C "cursor-cloud-agent@$(hostname)"
fi

# Ensure RunPod knows this key (idempotent).
runpodctl ssh add-key --key-file "${SSH_KEY}.pub" >/dev/null 2>&1 || \
  runpodctl ssh add-key --key-file "${SSH_KEY}.pub" || true

echo "looking up pod name=${POD_NAME} ..."
POD_JSON="$(runpodctl pod list --name "$POD_NAME" -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or data.get("data") or []
if isinstance(data, dict) and "id" in data:
    pods = [data]
if not pods:
    sys.stderr.write("no pod matched that name (is it running?)\n")
    sys.exit(1)
pod = pods[0]
print(pod.get("id") or pod.get("podId") or "")
PY
)"

if [[ -z "$POD_ID" ]]; then
  echo "could not parse pod id from: $POD_JSON" >&2
  exit 1
fi
echo "found pod id=${POD_ID}"

KNOWN_HOSTS="${HOME}/.ssh/known_hosts_runpod"
# Populated by resolve_ssh_target.
SSH_HOST=""
SSH_PORT=""
SSH_USER=""
SSH_OPTS=()

# RunPod may remap the public SSH port on restart, so the target is resolved
# via a function that can be re-run after `pod restart`.
resolve_ssh_target() {
  local info_json host="" port="" user=""
  info_json="$(runpodctl ssh info "$POD_ID" -o json)" || return 1
  eval "$(INFO_JSON="$info_json" python3 - <<'PY'
import json, os, shlex
info = json.loads(os.environ["INFO_JSON"])
host = info.get("ip") or info.get("host") or info.get("hostname") or ""
port = info.get("port") or info.get("sshPort") or 22
user = info.get("user") or info.get("username") or "root"
cmd = info.get("ssh_command") or info.get("command") or ""
if cmd and (not host):
    parts = cmd.split()
    for i, p in enumerate(parts):
        if p == "-p" and i + 1 < len(parts):
            port = parts[i + 1]
        if "@" in p and not p.startswith("-"):
            user, host = p.split("@", 1)
print(f"host={shlex.quote(str(host))}")
print(f"port={shlex.quote(str(port))}")
print(f"user={shlex.quote(str(user))}")
PY
)"
  if [[ -z "$host" ]]; then
    echo "ssh info missing host for pod ${POD_ID}: ${info_json}" >&2
    return 1
  fi
  SSH_HOST="$host"
  SSH_PORT="$port"
  SSH_USER="$user"
  SSH_OPTS=(
    -i "$SSH_KEY"
    -p "$SSH_PORT"
    -o StrictHostKeyChecking=accept-new
    -o UserKnownHostsFile="$KNOWN_HOSTS"
    -o IdentitiesOnly=yes
    -o ConnectTimeout=20
  )
}

# The pod presents a new host key after a restart; drop the cached one so
# accept-new does not refuse the reconnect.
forget_host_key() {
  [[ -f "$KNOWN_HOSTS" ]] || return 0
  ssh-keygen -R "[${SSH_HOST}]:${SSH_PORT}" -f "$KNOWN_HOSTS" >/dev/null 2>&1 || true
  ssh-keygen -R "$SSH_HOST" -f "$KNOWN_HOSTS" >/dev/null 2>&1 || true
}

resolve_ssh_target
echo "ssh ${SSH_USER}@${SSH_HOST} -p ${SSH_PORT}"

# Fresh pods may need a restart after add-key before authorized_keys is injected.
if ! ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" "true" 2>/dev/null; then
  echo "ssh failed; restarting pod so authorized_keys refreshes ..."
  runpodctl pod restart "$POD_ID" >/dev/null || true
  for _ in $(seq 1 36); do
    sleep 5
    resolve_ssh_target 2>/dev/null || continue
    forget_host_key
    if ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" "true" 2>/dev/null; then
      break
    fi
  done
  echo "ssh ${SSH_USER}@${SSH_HOST} -p ${SSH_PORT}"
fi

ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" "true"

# Stream the remote bootstrap script with required env.
ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" \
  env \
    CURSOR_API_KEY="$CURSOR_API_KEY" \
    WORKER_NAME="$WORKER_NAME" \
    REPO_URL="$REPO_URL" \
    WORKER_DIR="$WORKER_DIR" \
    bash -s \
  < "$REMOTE_SCRIPT"

echo
echo "Next: open https://cursor.com/agents and pick worker=${WORKER_NAME}"
echo "Or start a Cloud Agent with worker=${WORKER_NAME} for this repo."
