#!/usr/bin/env bash
# Start / status / stop the ECC2K-130 20 B/s GPU rho campaign on a RunPod.
#
# Required: RUNPOD_API_KEY
# Optional: POD_NAME (default solar_ivory_canidae), SSH_KEY, RUN_ID (16-bit)
#
# Usage:
#   ./scripts/runpod_deploy_ecc2k130.sh [start|status|stop]
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"
CMD="${1:-start}"
POD_NAME="${POD_NAME:-solar_ivory_canidae}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
RUN_ID="${RUN_ID:-4242}"
BIN_HOST="/root/ecc2k130-20b/bins/ecc2k130-rtx-pro6000-20b"
CAMP="/root/ecc2k130-campaign"
export PATH="${HOME}/.local/bin:${PATH}"

command -v runpodctl >/dev/null || { echo "runpodctl required" >&2; exit 1; }
[[ -f "$SSH_KEY" ]] || { echo "missing $SSH_KEY" >&2; exit 1; }

POD_JSON="$(runpodctl pod list --name "$POD_NAME" -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or []
if not pods:
    sys.exit("no running pod with that name")
print(pods[0]["id"])
PY
)"
INFO_JSON="$(runpodctl ssh info "$POD_ID" -o json)"
SSH_HOST=""
SSH_PORT=""
SSH_USER=""
eval "$(INFO_JSON="$INFO_JSON" python3 - <<'PY'
import json, os, shlex
info = json.loads(os.environ["INFO_JSON"])
print(f"SSH_HOST={shlex.quote(str(info.get('ip') or ''))}")
print(f"SSH_PORT={shlex.quote(str(info.get('port') or 22))}")
print(f"SSH_USER={shlex.quote(str(info.get('user') or 'root'))}")
PY
)"

ssh_pod() {
  ssh -i "$SSH_KEY" -p "$SSH_PORT" \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
    -o IdentitiesOnly=yes -o BatchMode=yes \
    "${SSH_USER}@${SSH_HOST}" "$@"
}

case "$CMD" in
  status)
    ssh_pod bash -s <<EOS
set -euo pipefail
tmux has-session -t '=ecc2k130-20b' 2>/dev/null && echo 'tmux=up' || echo 'tmux=down'
nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader || true
if [[ -f $CAMP/dps.bin ]]; then
  python3 -c "import os; n=os.path.getsize('$CAMP/dps.bin'); print(f'dps_records={n//32}')"
fi
tmux capture-pane -t ecc2k130-20b -p -S -15 2>/dev/null | tail -12 || true
EOS
    ;;
  stop)
    ssh_pod 'tmux kill-session -t "=ecc2k130-20b" 2>/dev/null || true; pkill -f ecc2k130-rtx-pro6000-20b 2>/dev/null || true; echo stopped'
    ;;
  start)
    ssh_pod env RUN_ID="$RUN_ID" BIN_HOST="$BIN_HOST" CAMP="$CAMP" bash -s <<'EOS'
set -euo pipefail
[[ -x "$BIN_HOST" ]] || { echo "missing binary $BIN_HOST" >&2; exit 1; }
mkdir -p "$CAMP"
cat > "$CAMP/start.sh" <<SH
#!/usr/bin/env bash
set -uo pipefail
BIN=$BIN_HOST
DP=$CAMP/dps.bin
CKPT=$CAMP/checkpoint.bin
LOG=$CAMP/run.log
echo "starting \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "\$LOG"
"\$BIN" \\
  --curve 131 \\
  --packed \\
  --dp-weight 34 \\
  --steps 1024 \\
  --launches 0 \\
  --verify 64 \\
  --run-id $RUN_ID \\
  --dp-file "\$DP" \\
  --checkpoint "\$CKPT" \\
  --checkpoint-every 300 \\
  2>&1 | tee -a "\$LOG"
echo "exited \$? at \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "\$LOG"
SH
chmod +x "$CAMP/start.sh"
tmux kill-session -t '=ecc2k130-20b' 2>/dev/null || true
pkill -f ecc2k130-rtx-pro6000-20b 2>/dev/null || true
sleep 1
tmux new-session -d -s ecc2k130-20b -c "$CAMP" -- bash "$CAMP/start.sh"
sleep 8
tmux capture-pane -t ecc2k130-20b -p -S -20 | tail -15
nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader
EOS
    ;;
  *)
    echo "usage: $0 [start|status|stop]" >&2
    exit 2
    ;;
esac
