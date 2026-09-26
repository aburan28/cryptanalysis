#!/usr/bin/env bash
# worker.sh - keep this pod's Cursor self-hosted worker connected.
#
# boot.sh runs this in the tmux session `cursor-worker`.  The worker registers
# under FLEET_WORKER_NAME, so `worker=<name>` in Slack/GitHub, the machine
# picker on cursor.com/agents, and `cloud/fleet.py agent <name>` all reach it.
# It is a personal ("My Machines") worker of whichever Cursor user signed it
# in: the owner of the API key in secrets/cursor-api-key when there is one,
# otherwise whoever opens the `agent login` link published in login-link.txt
# (`cloud/fleet.py login <name>` prints it).
set -uo pipefail

FLEET=/workspace/fleet
LOG="$FLEET/logs/worker.log"
KEY="$FLEET/secrets/cursor-api-key"
LINK="$FLEET/login-link.txt"
# shellcheck source=/dev/null
source "$FLEET/config.env"
# shellcheck source=/dev/null
source "$FLEET/env.sh"

gpu="${FLEET_GPU:-}"
labels=(--label "fleet=runpod" --label "cpus=${FLEET_CPUS:-$(nproc)}" --label "mem_gb=${FLEET_MEM_GB:-0}")
[[ -n "$gpu" ]] && labels+=(--label "gpu=${gpu// /_}")
IFS=',' read -r -a extra <<<"${FLEET_LABELS:-}"
for kv in "${extra[@]}"; do
  [[ -n "$kv" ]] && labels+=(--label "$kv")
done

signed_in() {
  agent status --format json 2>/dev/null |
    python3 -c 'import json, sys; sys.exit(0 if json.load(sys.stdin).get("isAuthenticated") else 1)'
}

sign_in() {
  while ! signed_in; do
    echo "waiting for a sign-in: open the link in $LINK" | tee -a "$LOG"
    NO_OPEN_BROWSER=1 agent login 2>&1 | while IFS= read -r line; do
      echo "$line" >>"$LOG"
      if [[ "$line" =~ (https://cursor\.com/loginDeepControl[^[:space:]]+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}" >"$LINK"
      fi
    done
  done
  rm -f "$LINK"
}

worker() {
  agent worker \
    --name "$FLEET_WORKER_NAME" \
    --worker-dir /workspace/cryptanalysis \
    --data-dir "$FLEET/agent" \
    --idle-release-timeout 0 \
    --management-addr 127.0.0.1:8787 \
    "${labels[@]}" \
    start --verbose 2>&1 | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

while true; do
  if [[ -f "$LOG" ]] && (($(stat -c %s "$LOG") > 50 * 1024 * 1024)); then
    mv -f "$LOG" "$LOG.1"
  fi
  echo "starting agent worker $(date -u +%FT%TZ)" | tee -a "$LOG"
  if [[ -s "$KEY" ]]; then
    CURSOR_API_KEY="$(cat "$KEY")" worker
  else
    sign_in
    worker
  fi
  echo "agent worker exited ($?) $(date -u +%FT%TZ); restarting in 15 s" | tee -a "$LOG"
  sleep 15
done
