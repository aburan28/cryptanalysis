#!/usr/bin/env bash
# job_runner.sh - run one shard of a remote job and package what it produced.
#
# cloud/modal_run.py and `cloud/fleet.py run` hand this script to bash on the
# remote side, with the job described in the environment:
#
#   JOB_DIR      where log.txt, status.json and out.tar.gz are written
#   JOB_WORKDIR  the directory the command runs in (the unpacked checkout)
#   JOB_CMD      the command, run with `bash -c`
#   JOB_SRC      optional tarball to unpack into JOB_WORKDIR first
#   JOB_OUTS     optional newline-separated paths, relative to JOB_WORKDIR,
#                to return (directories are returned whole)
#   JOB_CHANGED  1 to also return every file the command created or modified,
#                outside build trees and below 200 MB
#   JOB_ID, SHARD_INDEX, SHARD_COUNT   passed through to the command
#
# The exit status is the command's; 125 means the job could not be set up.
set -uo pipefail

: "${JOB_DIR:?}" "${JOB_WORKDIR:?}" "${JOB_CMD:?}"
export SHARD_INDEX="${SHARD_INDEX:-0}" SHARD_COUNT="${SHARD_COUNT:-1}"
export PYTHONUNBUFFERED=1
mkdir -p "$JOB_DIR" "$JOB_WORKDIR"
LOG="$JOB_DIR/log.txt"
note() { echo "== $*" | tee -a "$LOG"; }

if [[ -n "${JOB_SRC:-}" ]] && ! tar -xzf "$JOB_SRC" -C "$JOB_WORKDIR"; then
  note "cannot unpack $JOB_SRC"
  exit 125
fi
cd "$JOB_WORKDIR" || exit 125
marker="$JOB_DIR/.started"
touch "$marker"

cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')
mem_gb=$(awk '/MemTotal/ {printf "%.0f", $2 / 1048576}' /proc/meminfo)
gpus=$(command -v nvidia-smi >/dev/null 2>&1 &&
  nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | paste -sd ';' -)
note "job ${JOB_ID:-?} shard $SHARD_INDEX/$SHARD_COUNT on $(hostname) at $(date -u +%FT%TZ)"
note "$(nproc) CPUs ($cpu_model), $mem_gb GiB${gpus:+, GPU: $gpus}"
note "\$ $JOB_CMD"

started=$(date +%s.%N)
bash -c "$JOB_CMD" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
finished=$(date +%s.%N)
note "exit $rc after $(awk -v a="$started" -v b="$finished" 'BEGIN {printf "%.1f", b - a}') s"

list="$JOB_DIR/outputs.txt"
: >"$list"
if [[ -n "${JOB_OUTS:-}" ]]; then
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if [[ -e "$path" ]]; then
      find "$path" -type f >>"$list"
    else
      note "output $path was not produced"
    fi
  done <<<"$JOB_OUTS"
fi
if [[ "${JOB_CHANGED:-0}" == 1 ]]; then
  find . \( -name .git -o -name build -o -name 'build-*' -o -name target \
    -o -name __pycache__ -o -name node_modules \) -prune \
    -o -type f -newer "$marker" -size -200M -print | sed 's|^\./||' >>"$list"
fi
sort -u -o "$list" "$list"
count=$(wc -l <"$list")
if ((count > 0)); then
  if tar -czf "$JOB_DIR/out.tar.gz" -T "$list" 2>>"$LOG"; then
    note "returning $count files"
  else
    note "packing the outputs failed"
  fi
fi

python3 - "$JOB_DIR/status.json" "$rc" "$started" "$finished" "$count" \
  "$(hostname)" "$(nproc)" "$mem_gb" "$cpu_model" "${gpus:-}" <<'EOF' || true
import json, os, sys
path, rc, started, finished, count, host, cpus, mem_gb, cpu_model, gpus = sys.argv[1:]
with open(path, "w") as f:
    json.dump({"job": os.environ.get("JOB_ID"), "shard": int(os.environ["SHARD_INDEX"]),
               "shards": int(os.environ["SHARD_COUNT"]), "returncode": int(rc),
               "started": float(started), "finished": float(finished),
               "seconds": round(float(finished) - float(started), 3), "outputs": int(count),
               "host": host, "cpus": int(cpus), "mem_gb": int(mem_gb), "cpu_model": cpu_model,
               "gpus": [g for g in gpus.split(";") if g]}, f, indent=1)
EOF
sync "$JOB_DIR" 2>/dev/null || true
exit "$rc"
