#!/usr/bin/env bash
# Check whether the Cursor My Machines worker is alive on a named RunPod.
#
# Required env:
#   RUNPOD_API_KEY
#
# Optional env:
#   POD_NAME   (default: solar_ivory_canidae)
#   SSH_KEY    (default: ~/.ssh/id_ed25519)
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"

POD_NAME="${POD_NAME:-solar_ivory_canidae}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
export PATH="${HOME}/.local/bin:${PATH}"

command -v runpodctl >/dev/null || {
  echo "runpodctl not found; install via scripts/runpod_attach_cursor_worker.sh first" >&2
  exit 1
}

POD_JSON="$(runpodctl pod list --name "$POD_NAME" --all -o json)"
POD_ID=""
DESIRED=""
RUNTIME=""
eval "$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, shlex, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or data.get("data") or []
if isinstance(data, dict) and "id" in data:
    pods = [data]
if not pods:
    sys.stderr.write("no pod matched that name\n")
    sys.exit(1)
pod = pods[0]
print(f"POD_ID={shlex.quote(str(pod.get('id') or ''))}")
print(f"DESIRED={shlex.quote(str(pod.get('desiredStatus') or ''))}")
print(f"RUNTIME={shlex.quote(str(pod.get('runtimeStatus') or ''))}")
PY
)"

echo "pod=${POD_NAME} id=${POD_ID} desired=${DESIRED} runtime=${RUNTIME}"

if [[ "$DESIRED" != "RUNNING" && "$RUNTIME" != "running" ]]; then
  echo "pod is not running; start it before expecting a Cursor worker"
  exit 2
fi

if [[ ! -f "$SSH_KEY" ]]; then
  echo "missing SSH key at ${SSH_KEY}; cannot inspect tmux worker" >&2
  exit 1
fi

INFO_JSON="$(runpodctl ssh info "$POD_ID" -o json)"
SSH_HOST=""
SSH_PORT=""
SSH_USER=""
eval "$(INFO_JSON="$INFO_JSON" python3 - <<'PY'
import json, os, shlex
info = json.loads(os.environ["INFO_JSON"])
host = info.get("ip") or info.get("host") or info.get("hostname") or ""
port = info.get("port") or info.get("sshPort") or 22
user = info.get("user") or info.get("username") or "root"
print(f"SSH_HOST={shlex.quote(str(host))}")
print(f"SSH_PORT={shlex.quote(str(port))}")
print(f"SSH_USER={shlex.quote(str(user))}")
PY
)"

if [[ -z "$SSH_HOST" ]]; then
  echo "no ssh endpoint yet" >&2
  exit 1
fi

ssh -i "$SSH_KEY" -p "$SSH_PORT" \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  -o ConnectTimeout=15 \
  "${SSH_USER}@${SSH_HOST}" 'bash -s' <<'EOS'
set -euo pipefail
echo "hostname=$(hostname)"
if tmux has-session -t '=cursor-worker' 2>/dev/null; then
  echo "tmux=cursor-worker up"
  tmux capture-pane -t cursor-worker -p -S -30 | tail -20
else
  echo "tmux=cursor-worker missing"
  exit 3
fi
if pgrep -f 'agent.*worker' >/dev/null; then
  echo "agent_worker=running"
else
  echo "agent_worker=missing"
  exit 3
fi
EOS
