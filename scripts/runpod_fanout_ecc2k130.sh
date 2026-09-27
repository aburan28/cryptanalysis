#!/usr/bin/env bash
# Launch N ECC2K-130 20 B/s workers on a multi-GPU (or multi-MIG) RunPod.
#
# Default target: marginal_chocolate_ostrich (8× MIG 1g.24gb).
# Each worker gets one CUDA/MIG device, its own run-id, and its own campaign dir.
#
# Required: RUNPOD_API_KEY
# Optional:
#   POD_NAME          (default marginal_chocolate_ostrich)
#   WORKERS           (default 8; capped by visible MIG/GPU count)
#   BASE_RUN_ID       (default 5000; workers use BASE..BASE+N-1)
#   SSH_KEY           (default ~/.ssh/id_ed25519)
#   BIN_HOST          path to ecc2k130-rtx-pro6000-20b on the pod
#
# Usage:
#   ./scripts/runpod_fanout_ecc2k130.sh start|status|stop
# Prefer: ./scripts/cloud_launch.sh fanout start
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"

POD_NAME="${POD_NAME:-marginal_chocolate_ostrich}"
WORKERS="${WORKERS:-8}"
BASE_RUN_ID="${BASE_RUN_ID:-5000}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
BIN_HOST="${BIN_HOST:-/root/ecc2k130-20b/bins/ecc2k130-rtx-pro6000-20b}"
CAMP_ROOT="${CAMP_ROOT:-/root/ecc2k130-fanout}"
export PATH="${HOME}/.local/bin:${PATH}"

CMD="${1:-status}"

command -v runpodctl >/dev/null || { echo "runpodctl required" >&2; exit 1; }
[[ -f "$SSH_KEY" ]] || { echo "missing $SSH_KEY" >&2; exit 1; }

POD_JSON="$(runpodctl pod list --name "$POD_NAME" -a -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or data.get("data") or []
if isinstance(data, dict) and "id" in data:
    pods = [data]
running = [p for p in pods if str(p.get("desiredStatus") or "").upper() == "RUNNING"
           or str(p.get("runtimeStatus") or "").lower() == "running"]
pick = running or pods
if not pick:
    sys.exit("no pod matched that name")
print(pick[0].get("id") or "")
PY
)"
[[ -n "$POD_ID" ]] || { echo "could not resolve pod id for $POD_NAME" >&2; exit 1; }

ensure_ssh() {
  runpodctl ssh add-key --key-file "${SSH_KEY}.pub" >/dev/null 2>&1 || true
  local our_pub pod_get updated changed env_json
  our_pub="$(tr -d '\n' <"${SSH_KEY}.pub")"
  pod_get="$(runpodctl pod get "$POD_ID" -o json)"
  updated="$(POD_GET="$pod_get" OUR_PUB="$our_pub" python3 - <<'PY'
import json, os
pod = json.loads(os.environ["POD_GET"])
our = os.environ["OUR_PUB"].strip()
env = dict(pod.get("env") or {})
existing = env.get("PUBLIC_KEY") or ""
lines = [ln.strip() for ln in existing.splitlines() if ln.strip()]
bodies = {" ".join(ln.split()[:2]) for ln in lines}
our_body = " ".join(our.split()[:2])
changed = our_body not in bodies
if changed:
    lines.append(our)
    env["PUBLIC_KEY"] = "\n".join(lines) + "\n"
print(json.dumps({"changed": changed, "env": env}))
PY
)"
  changed="$(UPDATED="$updated" python3 -c 'import json,os; print(json.loads(os.environ["UPDATED"])["changed"])')"
  if [[ "$changed" == "True" ]]; then
    echo "merging SSH pubkey into $POD_NAME PUBLIC_KEY and restarting..."
    env_json="$(UPDATED="$updated" python3 -c 'import json,os; print(json.dumps(json.loads(os.environ["UPDATED"])["env"]))')"
    runpodctl pod update "$POD_ID" --env "$env_json" >/dev/null
    runpodctl pod restart "$POD_ID" >/dev/null
    sleep 25
  fi
}

refresh_ssh() {
  local info_json
  info_json="$(runpodctl ssh info "$POD_ID" -o json)"
  SSH_HOST=""
  SSH_PORT=""
  SSH_USER=""
  eval "$(INFO_JSON="$info_json" python3 - <<'PY'
import json, os, shlex
info = json.loads(os.environ["INFO_JSON"])
print(f"SSH_HOST={shlex.quote(str(info.get('ip') or ''))}")
print(f"SSH_PORT={shlex.quote(str(info.get('port') or 22))}")
print(f"SSH_USER={shlex.quote(str(info.get('user') or 'root'))}")
PY
)"
}

ssh_pod() {
  ssh -i "$SSH_KEY" -p "$SSH_PORT" \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20 \
    "${SSH_USER}@${SSH_HOST}" "$@"
}

wait_ssh() {
  local _try
  for _try in $(seq 1 36); do
    refresh_ssh
    if ssh_pod 'true' 2>/dev/null; then
      return 0
    fi
    sleep 5
  done
  echo "SSH still failing for $POD_NAME ($POD_ID)" >&2
  exit 1
}

case "$CMD" in
  status)
    ensure_ssh
    wait_ssh
    ssh_pod env CAMP_ROOT="$CAMP_ROOT" WORKERS="$WORKERS" BASE_RUN_ID="$BASE_RUN_ID" bash -s <<'EOS'
set -euo pipefail
echo "fanout root=$CAMP_ROOT"
nvidia-smi -L 2>/dev/null | head -40 || true
echo "--- workers ---"
for i in $(seq 0 $((WORKERS - 1))); do
  sess="ecc2k130-w${i}"
  camp="$CAMP_ROOT/w${i}"
  if tmux has-session -t "=$sess" 2>/dev/null; then
    state=up
  else
    state=down
  fi
  dps=0
  if [[ -f "$camp/dps.bin" ]]; then
    dps=$(python3 -c "import os; print(os.path.getsize('$camp/dps.bin')//32)")
  fi
  echo "w${i} run-id=$((BASE_RUN_ID + i)) tmux=$state dps=$dps"
  tmux capture-pane -t "$sess" -p -S -8 2>/dev/null | tail -4 | sed "s/^/  /" || true
done
EOS
    ;;
  stop)
    ensure_ssh
    wait_ssh
    ssh_pod env WORKERS="$WORKERS" bash -s <<'EOS'
set -euo pipefail
for i in $(seq 0 $((WORKERS - 1))); do
  tmux kill-session -t "=ecc2k130-w${i}" 2>/dev/null || true
done
pkill -f ecc2k130-rtx-pro6000-20b 2>/dev/null || true
echo stopped
EOS
    ;;
  start)
    ensure_ssh
    wait_ssh
    ssh_pod env \
      WORKERS="$WORKERS" \
      BASE_RUN_ID="$BASE_RUN_ID" \
      BIN_HOST="$BIN_HOST" \
      CAMP_ROOT="$CAMP_ROOT" \
      bash -s <<'EOS'
set -euo pipefail
[[ -x "$BIN_HOST" ]] || { echo "missing binary $BIN_HOST — copy ecc2k130-rtx-pro6000-20b first" >&2; exit 1; }
command -v tmux >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tmux; }

# Prefer MIG UUIDs when present (this pod is 8× 1g.24gb); else plain GPU indices.
mapfile -t DEVS < <(python3 - <<'PY'
import subprocess, re
out = subprocess.check_output(["nvidia-smi", "-L"], text=True)
migs = re.findall(r"UUID:\s*(MIG-[0-9a-fA-F-]+)", out)
if migs:
    for u in migs:
        print(u)
else:
    gpus = re.findall(r"^GPU\s+(\d+):", out, re.M)
    for g in gpus:
        print(g)
PY
)
N_DEV=${#DEVS[@]}
[[ "$N_DEV" -gt 0 ]] || { echo "no CUDA/MIG devices visible" >&2; exit 1; }
if [[ "$WORKERS" -gt "$N_DEV" ]]; then
  echo "requested WORKERS=$WORKERS but only $N_DEV devices; capping" >&2
  WORKERS=$N_DEV
fi
echo "launching $WORKERS workers on $N_DEV devices; base run-id=$BASE_RUN_ID"
mkdir -p "$CAMP_ROOT"

# Stop previous fanout.
for i in $(seq 0 31); do
  tmux kill-session -t "=ecc2k130-w${i}" 2>/dev/null || true
done
pkill -f ecc2k130-rtx-pro6000-20b 2>/dev/null || true
sleep 1

for i in $(seq 0 $((WORKERS - 1))); do
  dev="${DEVS[$i]}"
  rid=$((BASE_RUN_ID + i))
  camp="$CAMP_ROOT/w${i}"
  sess="ecc2k130-w${i}"
  mkdir -p "$camp"
  cat > "$camp/start.sh" <<SH
#!/usr/bin/env bash
set -uo pipefail
export CUDA_VISIBLE_DEVICES=$dev
BIN=$BIN_HOST
DP=$camp/dps.bin
CKPT=$camp/checkpoint.bin
LOG=$camp/run.log
echo "starting w$i device=$dev run-id=$rid \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "\$LOG"
"\$BIN" \\
  --curve 131 \\
  --packed \\
  --device 0 \\
  --dp-weight 34 \\
  --steps 1024 \\
  --launches 0 \\
  --verify 0 \\
  --run-id $rid \\
  --dp-file "\$DP" \\
  --checkpoint "\$CKPT" \\
  --checkpoint-every 300 \\
  2>&1 | tee -a "\$LOG"
echo "exited \$? at \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "\$LOG"
SH
  chmod +x "$camp/start.sh"
  tmux new-session -d -s "$sess" -c "$camp" -- bash "$camp/start.sh"
  echo "started $sess device=$dev run-id=$rid"
done

sleep 12
echo "--- status ---"
for i in $(seq 0 $((WORKERS - 1))); do
  sess="ecc2k130-w${i}"
  tmux has-session -t "=$sess" 2>/dev/null && st=up || st=down
  echo "w${i} tmux=$st"
  tmux capture-pane -t "$sess" -p -S -12 2>/dev/null | tail -6 | sed "s/^/  /" || true
done
EOS
    ;;
  *)
    echo "usage: $0 [start|status|stop]" >&2
    exit 2
    ;;
esac
