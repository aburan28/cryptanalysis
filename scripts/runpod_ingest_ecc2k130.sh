#!/usr/bin/env bash
# Run ECC2K-130 dp_ingest on the RunPod MiG pod named "ingest".
#
# The status page reads Postgres + status.json; GPU workers only write S3.
# This host copies s3://$BUCKET/dp/ into rho-dp via aws/ingest.sh (upstream
# crypto). Prefer the cheap MiG instance over burning a full GPU for ingest.
#
# Required: RUNPOD_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# Optional: INGEST_POD_NAME (default ingest), SSH_KEY, CRYPTO_DIR on pod,
#           ECC_BUCKET, ECC_STATUS_BUCKET, INGEST_THREADS
#
# Usage:
#   ./scripts/runpod_ingest_ecc2k130.sh start|status|stop|ensure-ssh
#
# Prefer: ./scripts/cloud_launch.sh ingest start
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"

INGEST_POD_NAME="${INGEST_POD_NAME:-ingest}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
CRYPTO_REMOTE="${CRYPTO_REMOTE:-/root/crypto}"
CRYPTO_REPO="${CRYPTO_REPO:-https://github.com/aburan28/crypto.git}"
INGEST_THREADS="${INGEST_THREADS:-6}"
TMUX_SESSION="${TMUX_SESSION:-ecc2k130-ingest}"
export PATH="${HOME}/.local/bin:${PATH}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Cursor / cloud-agent AWS secret aliases
if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -n "${Awskeyid:-}" ]]; then
  export AWS_ACCESS_KEY_ID="$Awskeyid"
fi
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${Awssecret:-}" ]]; then
  export AWS_SECRET_ACCESS_KEY="$Awssecret"
fi

CMD="${1:-status}"

command -v runpodctl >/dev/null || { echo "runpodctl required" >&2; exit 1; }
[[ -f "$SSH_KEY" ]] || { echo "missing $SSH_KEY" >&2; exit 1; }

POD_JSON="$(runpodctl pod list --name "$INGEST_POD_NAME" -a -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or data.get("data") or []
if isinstance(data, dict) and "id" in data:
    pods = [data]
# Prefer RUNNING
running = [p for p in pods if str(p.get("desiredStatus") or p.get("desired_status") or "").upper() == "RUNNING"
           or str(p.get("runtimeStatus") or "").lower() == "running"]
pick = (running or pods)
if not pick:
    sys.exit(f"no pod named {os.environ.get('INGEST_POD_NAME','ingest')}")
print(pick[0].get("id") or pick[0].get("podId") or "")
PY
)"
[[ -n "$POD_ID" ]] || { echo "could not resolve pod id for $INGEST_POD_NAME" >&2; exit 1; }

ensure_ssh() {
  # Account-level keys are not enough for an already-rented pod — merge into
  # PUBLIC_KEY and restart when the key was missing (same pattern as the
  # Cursor worker attach script).
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
    echo "merging SSH pubkey into $INGEST_POD_NAME PUBLIC_KEY and restarting..."
    env_json="$(UPDATED="$updated" python3 -c 'import json,os; print(json.dumps(json.loads(os.environ["UPDATED"])["env"]))')"
    runpodctl pod update "$POD_ID" --env "$env_json" >/dev/null
    runpodctl pod restart "$POD_ID" >/dev/null
    echo "waiting for SSH after restart..."
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
  [[ -n "$SSH_HOST" && "$SSH_HOST" != "None" ]] || {
    echo "no SSH endpoint yet for $INGEST_POD_NAME ($POD_ID); is it running?" >&2
    exit 1
  }
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
  echo "SSH still failing after wait (pod=$POD_ID host=$SSH_HOST port=$SSH_PORT)" >&2
  exit 1
}

case "$CMD" in
  ensure-ssh)
    ensure_ssh
    wait_ssh
    echo "SSH ok: ${SSH_USER}@${SSH_HOST}:${SSH_PORT} ($INGEST_POD_NAME / $POD_ID)"
    ;;
  status)
    ensure_ssh
    wait_ssh
    ssh_pod bash -s <<EOS
set -euo pipefail
echo "pod=$INGEST_POD_NAME id=$POD_ID"
tmux has-session -t '=$TMUX_SESSION' 2>/dev/null && echo 'tmux=up' || echo 'tmux=down'
nvidia-smi -L 2>/dev/null | head -3 || echo 'nvidia-smi: n/a (MiG / CPU-only ok for ingest)'
if [[ -f /root/ecc2k130-ingest/ingest.log ]]; then
  echo '--- ingest.log (tail) ---'
  tail -20 /root/ecc2k130-ingest/ingest.log
fi
tmux capture-pane -t '$TMUX_SESSION' -p -S -20 2>/dev/null | tail -15 || true
EOS
    ;;
  stop)
    ensure_ssh
    wait_ssh
    ssh_pod "tmux kill-session -t '=$TMUX_SESSION' 2>/dev/null || true; pkill -f dp_ingest.py 2>/dev/null || true; echo stopped"
    ;;
  start)
    : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required to run ingest}"
    : "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required to run ingest}"
    ensure_ssh
    wait_ssh

    # Install AWS creds + bootstrap crypto + start ingest in tmux.
    # Credentials go to ~/.aws/credentials (mode 600), not the process argv.
    ssh_pod env \
      AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
      ECC_BUCKET="${ECC_BUCKET:-}" \
      ECC_STATUS_BUCKET="${ECC_STATUS_BUCKET:-}" \
      CRYPTO_REMOTE="$CRYPTO_REMOTE" \
      CRYPTO_REPO="$CRYPTO_REPO" \
      INGEST_THREADS="$INGEST_THREADS" \
      TMUX_SESSION="$TMUX_SESSION" \
      bash -s <<'EOS'
set -euo pipefail
mkdir -p /root/.aws /root/ecc2k130-ingest
umask 077
cat > /root/.aws/credentials <<CREDS
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
CREDS
cat > /root/.aws/config <<CFG
[default]
region = ${AWS_DEFAULT_REGION}
CFG
chmod 600 /root/.aws/credentials /root/.aws/config

if ! command -v git >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git
fi
if ! command -v tmux >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tmux
fi

# Bootstrap venv for aws CLI only; ingest.sh creates its own INGEST_VENV.
BOOT_VENV=/root/ecc2k130-ingest/boot-venv
if [[ ! -x "$BOOT_VENV/bin/aws" ]]; then
  python3 -m venv "$BOOT_VENV"
  "$BOOT_VENV/bin/pip" install -q --upgrade pip
  "$BOOT_VENV/bin/pip" install -q awscli boto3
fi
export PATH="$BOOT_VENV/bin:$PATH"

if [[ ! -d "$CRYPTO_REMOTE/.git" ]]; then
  git clone --depth 1 "$CRYPTO_REPO" "$CRYPTO_REMOTE"
fi
git -C "$CRYPTO_REMOTE" fetch --depth 1 origin main
git -C "$CRYPTO_REMOTE" checkout -B ingest-deploy origin/main
test -f "$CRYPTO_REMOTE/ecc2k130/aws/ingest.sh"
test -f "$CRYPTO_REMOTE/ecc2k130/aws/dp_ingest.py"

BUCKET_EXPORT=""
STATUS_EXPORT=""
[[ -n "${ECC_BUCKET:-}" ]] && BUCKET_EXPORT="export ECC_BUCKET=${ECC_BUCKET}"
[[ -n "${ECC_STATUS_BUCKET:-}" ]] && STATUS_EXPORT="export ECC_STATUS_BUCKET=${ECC_STATUS_BUCKET}"

cat > /root/ecc2k130-ingest/start.sh <<SH
#!/usr/bin/env bash
set -uo pipefail
export PATH=/root/ecc2k130-ingest/boot-venv/bin:\$PATH
cd ${CRYPTO_REMOTE}/ecc2k130/aws
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
export INGEST_THREADS=${INGEST_THREADS}
export INGEST_ENSURE_ACCESS=1
export INGEST_VENV=/root/ecc2k130-ingest/venv
${BUCKET_EXPORT}
${STATUS_EXPORT}
echo "ingest start \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a /root/ecc2k130-ingest/ingest.log
./ingest.sh run 2>&1 | tee -a /root/ecc2k130-ingest/ingest.log
echo "ingest exited \$? at \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a /root/ecc2k130-ingest/ingest.log
SH
chmod +x /root/ecc2k130-ingest/start.sh

tmux kill-session -t "=$TMUX_SESSION" 2>/dev/null || true
pkill -f dp_ingest.py 2>/dev/null || true
sleep 1
tmux new-session -d -s "$TMUX_SESSION" -c /root/ecc2k130-ingest -- bash /root/ecc2k130-ingest/start.sh
sleep 12
echo "tmux=$TMUX_SESSION started"
tmux has-session -t "=$TMUX_SESSION" && echo tmux=up
tmux capture-pane -t "$TMUX_SESSION" -p -S -40 | tail -30
EOS
    ;;
  *)
    echo "usage: $0 [start|status|stop|ensure-ssh]" >&2
    exit 2
    ;;
esac
