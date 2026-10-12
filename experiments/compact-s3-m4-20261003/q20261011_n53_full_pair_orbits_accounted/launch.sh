#!/bin/sh
# Durable Q1452 replay: preserve logs and the worker's terminal exit code.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -e "$HERE/measurement.json" ] || [ -e "$HERE/exit-status.json" ]; then
    echo "Q1452 replay already has a terminal artifact" >&2
    exit 2
fi
if python3 "$HERE/run.py" --run > "$HERE/stdout.log" 2> "$HERE/stderr.log"; then
    code=0
else
    code=$?
fi
printf '{"exit_code":%s}\n' "$code" > "$HERE/exit-status.json.tmp"
mv "$HERE/exit-status.json.tmp" "$HERE/exit-status.json"
exit "$code"
