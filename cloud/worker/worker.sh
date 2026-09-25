#!/usr/bin/env bash
# worker.sh - keep this pod's Cursor self-hosted worker connected.
#
# boot.sh runs this in the tmux session `cursor-worker`.  The worker registers
# under FLEET_WORKER_NAME, so `worker=<name>` in Slack/GitHub, the machine
# picker on cursor.com/agents, and `cloud/fleet.py agent <name>` all reach it.
# It is a personal ("My Machines") worker: several agents may share it.
set -uo pipefail

FLEET=/workspace/fleet
LOG="$FLEET/logs/worker.log"
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

while true; do
  if [[ ! -s "$FLEET/secrets/cursor-api-key" ]]; then
    echo "no Cursor API key in $FLEET/secrets/cursor-api-key; retrying in 60 s"
    sleep 60
    continue
  fi
  if [[ -f "$LOG" ]] && (($(stat -c %s "$LOG") > 50 * 1024 * 1024)); then
    mv -f "$LOG" "$LOG.1"
  fi
  echo "starting agent worker $(date -u +%FT%TZ)" | tee -a "$LOG"
  CURSOR_API_KEY="$(cat "$FLEET/secrets/cursor-api-key")" \
    agent worker \
    --name "$FLEET_WORKER_NAME" \
    --worker-dir /workspace/cryptanalysis \
    --data-dir "$FLEET/agent" \
    --idle-release-timeout 0 \
    --management-addr 127.0.0.1:8787 \
    "${labels[@]}" \
    start --verbose 2>&1 | tee -a "$LOG"
  echo "agent worker exited (${PIPESTATUS[0]}) $(date -u +%FT%TZ); restarting in 15 s" | tee -a "$LOG"
  sleep 15
done
