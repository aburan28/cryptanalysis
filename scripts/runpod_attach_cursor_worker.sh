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
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) ASSET=runpodctl-linux-amd64 ;;
    aarch64|arm64) ASSET=runpodctl-linux-arm64 ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
  esac
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

# Ensure RunPod account knows this key (idempotent).
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

# Official templates inject authorized_keys from the pod's PUBLIC_KEY env at
# boot. Account-level `ssh add-key` alone is not enough for an already-rented
# pod — merge our pubkey into PUBLIC_KEY and restart when missing.
OUR_PUB="$(tr -d '\n' <"${SSH_KEY}.pub")"
NEED_RESTART=0
POD_GET="$(runpodctl pod get "$POD_ID" -o json)"
UPDATED_ENV="$(POD_GET="$POD_GET" OUR_PUB="$OUR_PUB" python3 - <<'PY'
import json, os, sys
pod = json.loads(os.environ["POD_GET"])
our = os.environ["OUR_PUB"].strip()
env = dict(pod.get("env") or {})
existing = env.get("PUBLIC_KEY") or ""
lines = [ln.strip() for ln in existing.splitlines() if ln.strip()]
# Match by key body (ignore trailing comment).
bodies = {" ".join(ln.split()[:2]) for ln in lines}
our_body = " ".join(our.split()[:2])
changed = our_body not in bodies
if changed:
    lines.append(our)
    env["PUBLIC_KEY"] = "\n".join(lines) + "\n"
print(json.dumps({"changed": changed, "env": env}))
PY
)"
CHANGED="$(UPDATED_ENV="$UPDATED_ENV" python3 -c 'import json,os; print(json.loads(os.environ["UPDATED_ENV"])["changed"])')"
if [[ "$CHANGED" == "True" ]]; then
  echo "merging SSH pubkey into pod PUBLIC_KEY env ..."
  ENV_JSON="$(UPDATED_ENV="$UPDATED_ENV" python3 -c 'import json,os; print(json.dumps(json.loads(os.environ["UPDATED_ENV"])["env"]))')"
  runpodctl pod update "$POD_ID" --env "$ENV_JSON" >/dev/null
  NEED_RESTART=1
fi

refresh_ssh_info() {
  INFO_JSON="$(runpodctl ssh info "$POD_ID" -o json)"
  # Pre-declare so shellcheck sees the assignments (values come from eval below).
  SSH_HOST=""
  SSH_PORT=""
  SSH_USER=""
  eval "$(INFO_JSON="$INFO_JSON" python3 - <<'PY'
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
print(f"SSH_HOST={shlex.quote(str(host))}")
print(f"SSH_PORT={shlex.quote(str(port))}")
print(f"SSH_USER={shlex.quote(str(user))}")
PY
)"
}

refresh_ssh_info
if [[ -z "$SSH_HOST" ]]; then
  echo "ssh info missing host for pod ${POD_ID}: ${INFO_JSON}" >&2
  exit 1
fi

ssh_ok() {
  [[ -n "${SSH_HOST:-}" && -n "${SSH_PORT:-}" ]] || return 1
  ssh -i "$SSH_KEY" -p "$SSH_PORT" \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o ConnectTimeout=10 \
    "${SSH_USER}@${SSH_HOST}" "true" 2>/dev/null
}

if [[ "$NEED_RESTART" -eq 1 ]] || ! ssh_ok; then
  echo "restarting pod ${POD_ID} so authorized_keys picks up PUBLIC_KEY ..."
  runpodctl pod restart "$POD_ID" >/dev/null || true
  for _ in $(seq 1 48); do
    sleep 5
    refresh_ssh_info
    if [[ -n "$SSH_HOST" ]] && ssh_ok; then
      echo "ssh ready on ${SSH_USER}@${SSH_HOST}:${SSH_PORT}"
      break
    fi
    echo "waiting for ssh ..."
  done
fi

if ! ssh_ok; then
  echo "ssh still failing for ${SSH_USER}@${SSH_HOST}:${SSH_PORT}" >&2
  exit 1
fi

echo "ssh ${SSH_USER}@${SSH_HOST} -p ${SSH_PORT}"

# Stream the remote bootstrap script with required env.
ssh -i "$SSH_KEY" -p "$SSH_PORT" \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  "${SSH_USER}@${SSH_HOST}" \
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
echo "Status: ./scripts/runpod_cursor_worker_status.sh"
