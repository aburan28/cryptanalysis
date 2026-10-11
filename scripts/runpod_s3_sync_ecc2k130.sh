#!/usr/bin/env bash
# Upload local RunPod ecc2k130 dps.bin corpora to S3 for the ingest host.
#
# Modal has modal_sync.py (volume → S3). RunPod workers write dps.bin on disk;
# this installs a small incremental uploader in tmux on the target pod so
# ingest / the status page see those points too.
#
# Required: RUNPOD_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# Optional: POD_NAME (default marginal_chocolate_ostrich),
#           CAMP_ROOT (/root/ecc2k130-fanout for fanout, /root/ecc2k130-campaign for single),
#           SLOT_BASE (default 80000), SYNC_INTERVAL (60)
#
# Usage:
#   POD_NAME=marginal_chocolate_ostrich CAMP_ROOT=/root/ecc2k130-fanout \
#     ./scripts/runpod_s3_sync_ecc2k130.sh start|status|stop
#   POD_NAME=solar_ivory_canidae CAMP_ROOT=/root/ecc2k130-campaign WORKERS=1 \
#     BASE_RUN_ID=4242 ./scripts/runpod_s3_sync_ecc2k130.sh start
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"

POD_NAME="${POD_NAME:-marginal_chocolate_ostrich}"
CAMP_ROOT="${CAMP_ROOT:-/root/ecc2k130-fanout}"
WORKERS="${WORKERS:-8}"
BASE_RUN_ID="${BASE_RUN_ID:-5000}"
SLOT_BASE="${SLOT_BASE:-80000}"
SYNC_INTERVAL="${SYNC_INTERVAL:-60}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
TMUX_SESSION="${TMUX_SESSION:-ecc2k130-s3-sync}"
ECC_BUCKET="${ECC_BUCKET:-}"
export PATH="${HOME}/.local/bin:${PATH}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" && -n "${Awskeyid:-}" ]]; then
  export AWS_ACCESS_KEY_ID="$Awskeyid"
fi
if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" && -n "${Awssecret:-}" ]]; then
  export AWS_SECRET_ACCESS_KEY="$Awssecret"
fi

CMD="${1:-status}"

command -v runpodctl >/dev/null || { echo "runpodctl required" >&2; exit 1; }
[[ -f "$SSH_KEY" ]] || { echo "missing $SSH_KEY" >&2; exit 1; }
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY required}"

POD_JSON="$(runpodctl pod list --name "$POD_NAME" -a -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or []
if isinstance(data, dict) and "id" in data:
    pods = [data]
running = [p for p in pods if str(p.get("desiredStatus") or "").upper() == "RUNNING"
           or str(p.get("runtimeStatus") or "").lower() == "running"]
pick = running or pods
if not pick:
    sys.exit("no pod matched")
print(pick[0]["id"])
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
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20 \
    "${SSH_USER}@${SSH_HOST}" "$@"
}

case "$CMD" in
  status)
    ssh_pod env TMUX_SESSION="$TMUX_SESSION" bash -s <<'EOS'
set -euo pipefail
tmux has-session -t "=$TMUX_SESSION" 2>/dev/null && echo "tmux=up" || echo "tmux=down"
tail -20 /root/ecc2k130-s3-sync/sync.log 2>/dev/null || true
tmux capture-pane -t "$TMUX_SESSION" -p -S -15 2>/dev/null | tail -12 || true
EOS
    ;;
  stop)
    ssh_pod "tmux kill-session -t '=$TMUX_SESSION' 2>/dev/null || true; pkill -f runpod_dp_s3_sync.py 2>/dev/null || true; echo stopped"
    ;;
  start)
    ssh_pod env \
      AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
      ECC_BUCKET="${ECC_BUCKET}" \
      CAMP_ROOT="$CAMP_ROOT" \
      WORKERS="$WORKERS" \
      BASE_RUN_ID="$BASE_RUN_ID" \
      SLOT_BASE="$SLOT_BASE" \
      SYNC_INTERVAL="$SYNC_INTERVAL" \
      TMUX_SESSION="$TMUX_SESSION" \
      bash -s <<'EOS'
set -euo pipefail
mkdir -p /root/.aws /root/ecc2k130-s3-sync
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

command -v tmux >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq tmux; }
BOOT=/root/ecc2k130-s3-sync/venv
if [[ ! -x "$BOOT/bin/python3" ]]; then
  python3 -m venv "$BOOT"
  "$BOOT/bin/pip" install -q --upgrade pip
  "$BOOT/bin/pip" install -q boto3
fi

# Resolve bucket if unset.
if [[ -z "${ECC_BUCKET:-}" ]]; then
  ECC_BUCKET=$("$BOOT/bin/python3" -c 'import boto3; print("ecc2k130-"+boto3.client("sts").get_caller_identity()["Account"])')
fi

cat > /root/ecc2k130-s3-sync/runpod_dp_s3_sync.py <<'PY'
#!/usr/bin/env python3
"""Incremental upload of local dps.bin files into the ecc2k-seed-orbit-v1 layout."""
from __future__ import annotations
import hashlib, json, os, sys, time

RECORD = 32

def log(msg):
    sys.stderr.write(time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + msg + "\n")
    sys.stderr.flush()

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def stream_id(run_id):
    return hashlib.sha256(("runpod-run-%d" % run_id).encode()).hexdigest()[:32]

def orbit_key(slot, run_id, offset, path):
    return "dp/slot-%05d/%s-%016d-%s.bin" % (slot, stream_id(run_id), offset, sha256_file(path))

def state_path(state_dir, run_id):
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, "run-%d.json" % run_id)

def load_state(path):
    if not os.path.isfile(path):
        return {"offset": 0, "uploaded_records": 0}
    with open(path) as fh:
        return json.load(fh)

def save_state(path, state):
    tmp = path + ".part"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)

def sync_one(s3, bucket, dps_path, run_id, slot, state_dir):
    if not os.path.isfile(dps_path):
        return {"offset": 0, "uploaded_records": 0, "pending": False, "missing": True}
    st = load_state(state_path(state_dir, run_id))
    offset = int(st.get("offset", 0))
    size = os.path.getsize(dps_path)
    whole = size - size % RECORD
    if whole <= offset:
        return {"offset": offset, "uploaded_records": 0, "pending": False}
    import tempfile
    uploaded = 0
    objects = 0
    with tempfile.TemporaryDirectory(prefix="rp-s3-") as tmp:
        while offset < whole:
            delta = os.path.join(tmp, "delta-%d.bin" % offset)
            with open(dps_path, "rb") as src, open(delta, "wb") as out:
                src.seek(offset)
                out.write(src.read(whole - offset))
            key = orbit_key(slot, run_id, offset, delta)
            records = os.path.getsize(delta) // RECORD
            s3.upload_file(delta, bucket, key)
            log("uploaded %d records to s3://%s/%s" % (records, bucket, key))
            offset += records * RECORD
            uploaded += records
            objects += 1
    st.update(offset=offset,
              uploaded_records=int(st.get("uploaded_records", 0)) + uploaded,
              last_sync=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              slot=slot, bucket=bucket)
    save_state(state_path(state_dir, run_id), st)
    return {"offset": offset, "uploaded_records": uploaded, "objects": objects, "pending": True}

def main():
    import boto3
    bucket = os.environ["ECC_BUCKET"]
    camp = os.environ["CAMP_ROOT"]
    workers = int(os.environ.get("WORKERS", "1"))
    base = int(os.environ.get("BASE_RUN_ID", "5000"))
    slot_base = int(os.environ.get("SLOT_BASE", "80000"))
    interval = float(os.environ.get("SYNC_INTERVAL", "60"))
    state_dir = os.environ.get("STATE_DIR", "/root/ecc2k130-s3-sync/state")
    s3 = boto3.client("s3")
    log("runpod-s3-sync camp=%s workers=%d base_run=%d slot_base=%d → s3://%s/dp/"
        % (camp, workers, base, slot_base, bucket))
    while True:
        for i in range(workers):
            run_id = base + i
            slot = slot_base + run_id
            if workers == 1 and os.path.isfile(os.path.join(camp, "dps.bin")):
                dps = os.path.join(camp, "dps.bin")
            else:
                dps = os.path.join(camp, "w%d" % i, "dps.bin")
                if not os.path.isfile(dps) and os.path.isfile(os.path.join(camp, "dps.bin")):
                    dps = os.path.join(camp, "dps.bin")
            try:
                r = sync_one(s3, bucket, dps, run_id, slot, state_dir)
                if r.get("uploaded_records"):
                    print(json.dumps({run_id: r}), flush=True)
            except Exception as exc:
                log("run %d failed: %s: %s" % (run_id, type(exc).__name__, exc))
        time.sleep(interval)

if __name__ == "__main__":
    main()
PY
chmod +x /root/ecc2k130-s3-sync/runpod_dp_s3_sync.py

cat > /root/ecc2k130-s3-sync/start.sh <<SH
#!/usr/bin/env bash
set -uo pipefail
export PATH=/root/ecc2k130-s3-sync/venv/bin:\$PATH
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
export ECC_BUCKET=${ECC_BUCKET}
export CAMP_ROOT=${CAMP_ROOT}
export WORKERS=${WORKERS}
export BASE_RUN_ID=${BASE_RUN_ID}
export SLOT_BASE=${SLOT_BASE}
export SYNC_INTERVAL=${SYNC_INTERVAL}
export STATE_DIR=/root/ecc2k130-s3-sync/state
echo "s3-sync start \$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a /root/ecc2k130-s3-sync/sync.log
while true; do
  /root/ecc2k130-s3-sync/venv/bin/python3 /root/ecc2k130-s3-sync/runpod_dp_s3_sync.py \\
    2>&1 | tee -a /root/ecc2k130-s3-sync/sync.log
  echo "s3-sync exited \$? at \$(date -u +%Y-%m-%dT%H:%M:%SZ); restarting in 5s" | tee -a /root/ecc2k130-s3-sync/sync.log
  sleep 5
done
SH
chmod +x /root/ecc2k130-s3-sync/start.sh

tmux kill-session -t "=$TMUX_SESSION" 2>/dev/null || true
pkill -f runpod_dp_s3_sync.py 2>/dev/null || true
sleep 1
tmux new-session -d -s "$TMUX_SESSION" -c /root/ecc2k130-s3-sync -- bash /root/ecc2k130-s3-sync/start.sh
sleep 8
echo "tmux=$TMUX_SESSION bucket=$ECC_BUCKET camp=$CAMP_ROOT workers=$WORKERS"
tmux capture-pane -t "$TMUX_SESSION" -p -S -20 | tail -15
EOS
    ;;
  *)
    echo "usage: $0 [start|status|stop]" >&2
    exit 2
    ;;
esac
