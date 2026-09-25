#!/usr/bin/env bash
# boot.sh - bring a fleet pod up as a Cursor self-hosted worker.
#
# The pod's start command (STAGE0 in cloud/fleet.py) refreshes the fleet
# source under /workspace/fleet/src and runs this in the background at every
# container start.  Run it again over SSH to re-apply a change:
#
#   bash /workspace/fleet/src/cloud/worker/boot.sh [--restart]
#
# Only /workspace survives a pod stop, so everything slow to rebuild lives
# there and everything on the container disk (apt packages, /etc, /root) is
# re-created here.  Configuration arrives as pod environment variables
# (FLEET_*, CURSOR_API_KEY, optional GITHUB_TOKEN); they are copied under
# /workspace/fleet so that a later manual run sees the same values.
set -uo pipefail

FLEET=/workspace/fleet
SRC="$FLEET/src"
LOGS="$FLEET/logs"
SECRETS="$FLEET/secrets"
PHOME=/workspace/home
WORKDIR=/workspace/cryptanalysis
RESTART=0
[[ "${1:-}" == "--restart" ]] && RESTART=1

mkdir -p "$FLEET" "$LOGS" "$SECRETS" "$PHOME" /workspace/jobs /workspace/opt
chmod 700 "$SECRETS"

exec 9>"$FLEET/boot.lock"
if ! flock -n 9; then
  echo "boot.sh is already running"
  exit 0
fi

log() { printf '[fleet boot %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# ---- configuration ---------------------------------------------------------
CONFIG="$FLEET/config.env"
CONFIG_VARS=(FLEET_WORKER_NAME FLEET_REPO FLEET_REF FLEET_FALLBACK_REF
             FLEET_WORKER_BRANCH FLEET_FEATURES FLEET_LABELS
             FLEET_IDLE_STOP_MINUTES FLEET_GIT_NAME FLEET_GIT_EMAIL)
if [[ -n "${FLEET_WORKER_NAME:-}" ]]; then
  for v in "${CONFIG_VARS[@]}"; do
    printf '%s=%q\n' "$v" "${!v:-}"
  done >"$CONFIG"
fi
if [[ ! -f "$CONFIG" ]]; then
  log "no FLEET_WORKER_NAME in the environment and no saved $CONFIG"
  exit 1
fi
# shellcheck source=/dev/null
source "$CONFIG"

save_secret() {
  [[ -n "$2" ]] || return 0
  (umask 077 && printf '%s' "$2" >"$SECRETS/$1")
}
save_secret cursor-api-key "${CURSOR_API_KEY:-}"
save_secret github-token "${GITHUB_TOKEN:-}"
# The pod's own scoped key, if Runpod injected one, lets idle.py stop the pod.
save_secret runpod-api-key "${RUNPOD_API_KEY:-}"
save_secret runpod-pod-id "${RUNPOD_POD_ID:-}"

log "worker ${FLEET_WORKER_NAME} (features: ${FLEET_FEATURES:-none})"

# ---- minimal packages to get the worker online --------------------------------
export DEBIAN_FRONTEND=noninteractive
APT_ARCHIVES="$FLEET/apt-archives"
mkdir -p "$APT_ARCHIVES/partial"
need=()
for tool in tmux git curl jq python3 flock; do
  command -v "$tool" >/dev/null 2>&1 || need+=("$tool")
done
if ((${#need[@]})); then
  log "installing base packages for: ${need[*]}"
  apt-get update -qq
  apt-get -o Dir::Cache::Archives="$APT_ARCHIVES" install -y -qq --no-install-recommends \
    tmux git curl ca-certificates jq python3 util-linux procps >/dev/null
fi

# ---- persistent home ----------------------------------------------------------
# /root is on the container disk; keep the tool directories on the volume.
link_home() {
  local name=$1 target="$PHOME/$1" link="/root/$1"
  if [[ -e "$link" && ! -L "$link" ]]; then
    if [[ -d "$link" ]]; then
      mkdir -p "$target"
      cp -an "$link/." "$target/" 2>/dev/null || true
      rm -rf "$link"
    elif [[ ! -e "$target" ]]; then
      mv "$link" "$target"
    else
      rm -f "$link"
    fi
  fi
  if [[ ! -e "$target" ]]; then
    case "$name" in
      .*rc | .gitconfig) touch "$target" ;;
      *) mkdir -p "$target" ;;
    esac
  fi
  ln -sfn "$target" "$link"
}
for name in .cargo .rustup .local .cache .config .gitconfig; do
  link_home "$name"
done

git config --global user.name "${FLEET_GIT_NAME:-Cursor Agent}"
git config --global user.email "${FLEET_GIT_EMAIL:-cursoragent@cursor.com}"
git config --global safe.directory '*'
if [[ -s "$SECRETS/github-token" ]]; then
  (umask 077 && printf 'https://x-access-token:%s@github.com\n' \
    "$(cat "$SECRETS/github-token")" >"$SECRETS/git-credentials")
  git config --global credential.helper "store --file=$SECRETS/git-credentials"
fi

# ---- the checkout agents work in ----------------------------------------------
if [[ ! -d "$WORKDIR/.git" ]]; then
  log "cloning ${FLEET_REPO} into ${WORKDIR}"
  if git clone -q "$FLEET_REPO" "$WORKDIR"; then
    git -C "$WORKDIR" checkout -q "${FLEET_WORKER_BRANCH}" 2>/dev/null || true
  else
    log "clone failed; the worker will start without a checkout"
  fi
fi

# ---- the Cursor CLI -------------------------------------------------------------
export PATH="/root/.local/bin:$PATH"
# A GPU pod's /workspace is a network filesystem that refuses chown, which
# tar attempts when root unpacks an archive it did not create.
export TAR_OPTIONS=--no-same-owner
if ! command -v agent >/dev/null 2>&1; then
  log "installing the Cursor CLI"
  curl -fsS https://cursor.com/install | bash
fi
log "cursor CLI: $(agent --version 2>/dev/null || echo missing)"

# ---- the machine, as agents see it ------------------------------------------------
cpus="${RUNPOD_CPU_COUNT:-}"
if [[ -z "$cpus" && -r /sys/fs/cgroup/cpu.max ]]; then
  read -r quota period </sys/fs/cgroup/cpu.max
  [[ "$quota" != max ]] && cpus=$(((quota + period - 1) / period))
fi
cpus="${cpus:-$(nproc)}"
mem_gb="${RUNPOD_MEM_GB:-}"
if [[ -z "$mem_gb" && -r /sys/fs/cgroup/memory.max ]]; then
  limit=$(cat /sys/fs/cgroup/memory.max)
  [[ "$limit" != max ]] && mem_gb=$((limit / 1073741824))
fi
# /proc/meminfo shows the host's memory, not the pod's share; it is a last resort.
mem_gb="${mem_gb:-$(awk '/MemTotal/ {print int($2 / 1048576)}' /proc/meminfo)}"
gpu=""
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null |
    sort | uniq -c | awk '{n=$1; $1=""; sub(/^ /, ""); printf "%s%dx %s", sep, n, $0; sep="; "}')
fi

cat >"$FLEET/env.sh" <<EOF
# Written by cloud/worker/boot.sh; sourced by the Cursor worker and by shells.
export FLEET_WORKER_NAME=$(printf '%q' "$FLEET_WORKER_NAME")
export FLEET_CPUS=$cpus
export FLEET_MEM_GB=$mem_gb
export FLEET_GPU=$(printf '%q' "$gpu")
export CARGO_HOME=/root/.cargo
export RUSTUP_HOME=/root/.rustup
export MSOLVE=/workspace/opt/msolve/bin/msolve
export CUDA13_HOME=/workspace/opt/cuda-13.3
export PYTHONUNBUFFERED=1
export TAR_OPTIONS=--no-same-owner
case ":\$PATH:" in
  *:/workspace/venv/bin:*) ;;
  *) export PATH="/workspace/venv/bin:/root/.cargo/bin:/root/.local/bin:/workspace/opt/msolve/bin:\$PATH" ;;
esac
EOF
ln -sfn "$FLEET/env.sh" /etc/profile.d/zz-fleet.sh
grep -qs 'fleet/env.sh' /root/.bashrc ||
  echo '[ -f /workspace/fleet/env.sh ] && . /workspace/fleet/env.sh' >>/root/.bashrc

python3 - "$FLEET/machine.json" "$FLEET_WORKER_NAME" "$cpus" "$mem_gb" "$gpu" \
  "${RUNPOD_POD_ID:-}" <<'EOF'
import json, sys
path, worker, cpus, mem_gb, gpu, pod = sys.argv[1:]
with open(path, "w") as f:
    json.dump({"worker": worker, "cpus": int(cpus), "mem_gb": int(mem_gb),
               "gpu": gpu or None, "pod_id": pod or None}, f, indent=1)
EOF
log "machine: ${cpus} CPUs, ${mem_gb} GiB${gpu:+, $gpu}"

# ---- long-running sessions ---------------------------------------------------------
session() {
  local name=$1
  shift
  if tmux has-session -t "=$name" 2>/dev/null; then
    ((RESTART)) || return 0
    tmux kill-session -t "=$name"
  fi
  tmux new-session -d -s "$name" -c /workspace -- "$@"
  log "started tmux session $name"
}
session cursor-worker bash "$SRC/cloud/worker/worker.sh"
if [[ "${FLEET_IDLE_STOP_MINUTES:-0}" =~ ^[0-9]+$ ]] && ((FLEET_IDLE_STOP_MINUTES > 0)); then
  session fleet-idle python3 "$SRC/cloud/worker/idle.py"
fi
session fleet-toolchain bash -c \
  "bash '$SRC/cloud/worker/toolchain.sh' 2>&1 | tee -a '$LOGS/toolchain.log'"
log "boot complete"
