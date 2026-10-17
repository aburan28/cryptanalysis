#!/bin/sh
# Commit and push the given output files every INTERVAL seconds while process PID is alive,
# then once more after it exits, so partial results survive a reclaimed container.
#   checkpoint.sh PID INTERVAL "commit subject" FILE...
pid=$1; interval=$2; subject=$3; shift 3
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
# resolve the files against the caller's directory: git -C would read them relative to the repo root
abs=""; for f in "$@"; do abs="$abs $(cd "$(dirname "$f")" && pwd)/$(basename "$f")"; done
set -- $abs
snap() {
    git -C "$repo" add -- "$@" || echo "checkpoint: git add failed" >&2
    if ! git -C "$repo" diff --cached --quiet; then
        git -C "$repo" commit -q -m "$subject ($(date -u +%H:%MZ))" \
            -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VEprGCrEcYQ9V66SSU9G4D" -- "$@" &&
        for t in 2 4 8 16; do git -C "$repo" push -q && break; sleep $t; done
        echo "checkpoint $(date -u +%H:%M:%S)"
    fi
}
snap "$@"
while kill -0 "$pid" 2>/dev/null; do sleep "$interval"; snap "$@"; done
snap "$@"; echo "process $pid exited; final checkpoint done"
