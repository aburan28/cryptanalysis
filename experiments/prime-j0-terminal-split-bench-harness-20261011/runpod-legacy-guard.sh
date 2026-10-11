#!/usr/bin/env bash
set -euo pipefail

legacy_pid=19623
legacy_exe=/workspace/build/cryptominisat-5.14.7-gcc10/cryptominisat5
runner=/workspace/isolated-bench/staging/isolated_bench.3ac5727c3.py
queue=/workspace/isolated-bench
shared_lock=/workspace/experiment-runs/.serial.lock

while [[ -e /proc/${legacy_pid}/exe ]]; do
    current=$(readlink /proc/${legacy_pid}/exe || true)
    if [[ "$current" != "$legacy_exe" ]]; then
        break
    fi
    sleep 30
done

exec python3 -u "$runner" --queue-root "$queue" --shared-job-lock "$shared_lock" serve
