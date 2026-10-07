#!/usr/bin/env bash
# cairn_runner.sh - a cairn runner on a Runpod pod: cairn's host agent, which
# runs the jobs `cloud/cairn_queue.py submit` drops into its spool, one at a
# time, and registers the machine with a cairn node.
#
# cloud/runpod_pod.py's STAGE0 starts it in the background at every container
# start (POD_BOOT_B64), with:
#
#   CAIRN_RUNNER_NAME    the host name the agent registers under (the pod's name)
#   CAIRN_VERSION        the cairn release, checked against its published sha256
#   CAIRN_AGENT_NODES    comma-separated node URLs to register with; empty runs a
#                        private node on 127.0.0.1:8080 and registers there
#   RUNNER_IDLE_MINUTES  stop the pod after this long with nothing queued,
#                        running or unfetched and nobody logged in (0: never)
#
# Everything is under /root/runner: agent/jobs/{queue,running,done} is cairn's
# spool, trees/ the checkouts jobs unpack, checkout/ where they run, node/ the
# private node's data, *.log the output of each process.
set -uo pipefail

ROOT=/root/runner
mkdir -p "$ROOT/trees" "$ROOT/specs"
log() { printf '%s cairn-runner: %s\n' "$(date -u +%FT%TZ)" "$*"; }

# The pod's share of the machine, which unconfined jobs inherit for their
# records: nproc and /proc/meminfo report the host's.
cpus=${RUNPOD_CPU_COUNT:-}
if [[ -z $cpus && -r /sys/fs/cgroup/cpu.max ]]; then
  read -r quota period </sys/fs/cgroup/cpu.max
  if [[ $quota != max ]]; then cpus=$(((quota + period - 1) / period)); fi
fi
mem_gb=${RUNPOD_MEM_GB:-}
if [[ -z $mem_gb && -r /sys/fs/cgroup/memory.max ]]; then
  limit=$(cat /sys/fs/cgroup/memory.max)
  if [[ $limit != max ]]; then mem_gb=$((limit / 1073741824)); fi
fi
export FLEET_CPUS=${cpus:-$(nproc)}
export FLEET_MEM_GB=${mem_gb:-$(awk '/MemTotal/ {print int($2 / 1048576)}' /proc/meminfo)}
FLEET_GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | paste -sd ';' -)
export FLEET_GPU
log "$FLEET_CPUS CPUs, $FLEET_MEM_GB GB${FLEET_GPU:+, GPU: $FLEET_GPU}"

# The musl release, checked against its published sha256 as cairn's own
# Runpod seed does.  A container start may have wiped the last install.
install_cairn() {
  local tarball="cairn-v${CAIRN_VERSION}-x86_64-unknown-linux-musl.tar.gz" dir rc
  local url="https://github.com/aburan28/cairn/releases/download/v${CAIRN_VERSION}/$tarball"
  dir=$(mktemp -d)
  curl -fsSL -o "$dir/$tarball" "$url" &&
    curl -fsSL -o "$dir/$tarball.sha256" "$url.sha256" &&
    (cd "$dir" && sha256sum -c --quiet "$tarball.sha256" && tar -xzf "$tarball") &&
    install -m 0755 "$dir/cairn" /usr/local/bin/cairn
  rc=$?
  rm -rf "$dir"
  return "$rc"
}
until install_cairn; do
  log "could not install cairn $CAIRN_VERSION; retrying in 30 s"
  sleep 30
done
log "$(cairn --version | head -1)"

if [[ -z ${CAIRN_AGENT_NODES:-} ]]; then
  # A node for this runner alone: HTTP and p2p on loopback, and no seeds,
  # beacon or port mapping, so it dials nobody and nobody reaches it.
  (
    export CAIRN_DATA=$ROOT/node CAIRN_SEEDS=off CAIRN_BEACON_PORT=off CAIRN_PORTMAP=off
    export CAIRN_ROLES=coordinator
    while true; do
      cairn run --no-mcp --listen 127.0.0.1:9000 --serve 127.0.0.1:8080 >>"$ROOT/node.log" 2>&1
      log "node exited $?; restarting in 5 s"
      sleep 5
    done
  ) &
  export CAIRN_AGENT_NODES=http://127.0.0.1:8080
  for _ in $(seq 60); do
    curl -fs -o /dev/null http://127.0.0.1:8080/hosts && break
    sleep 1
  done
fi

# --sandbox none: a pod is a container with no engine or KVM inside, so the
# pod is the jail; jobs ask for `none` and their receipts say so.
(
  while true; do
    cairn agent run --data-dir "$ROOT/agent" --name "$CAIRN_RUNNER_NAME" --roles executor \
      --sandbox none --parallel 1 >>"$ROOT/agent.log" 2>&1
    log "agent exited $?; restarting in 5 s"
    sleep 5
  done
) &
log "agent started; registering with $CAIRN_AGENT_NODES"

busy() {
  local spool=$ROOT/agent/jobs dir
  compgen -G "$spool/queue/*.json" >/dev/null && return 0
  [[ -n $(ls -A "$spool/running" 2>/dev/null) ]] && return 0
  for dir in "$spool"/done/*/; do
    [[ -d $dir && ! -e $dir/.fetched ]] && return 0
  done
  pgrep -f 'sshd: root@' >/dev/null
}

idle=${RUNNER_IDLE_MINUTES:-0}
if ((idle > 0)); then
  last=$(date +%s)
  while sleep 60; do
    if busy; then
      last=$(date +%s)
    elif (($(date +%s) - last >= idle * 60)); then
      log "idle for $idle minutes; stopping the pod"
      curl -s https://api.runpod.io/graphql -H 'Content-Type: application/json' \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id } }\"}"
      last=$(date +%s)
    fi
  done
fi
wait
