#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
sage_root="$repo/third_party/sage-binary"
checker="$repo/experiments/sage-binary-arithmetic/runtime_check.py"
manifest="$repo/experiments/sage-binary-arithmetic/runtime-current.json"
test -x "$sage_root/venv/bin/python3" || { echo 'Linux Sage is not installed' >&2; exit 1; }
test -f "$manifest" || { echo 'Linux Sage is not accepted' >&2; exit 1; }
unset SAGE_ROOT SAGE_LOCAL SAGE_VENV SAGE_SRC SAGE_LIB SAGE_ENV_SOURCED PYTHONPATH PYTHONHOME PYTHONUSERBASE
export PYTHONNOUSERSITE=1
export PATH="$repo:$PATH"
export SAGE_LOCAL_RUNTIME_LAUNCHER="$repo/sage"
export SAGE_LOCAL_RUNTIME_MANIFEST="$manifest"
export DOT_SAGE="${MODAL_SAGE_CACHE:-/tmp/modal-sage-cache}"
mkdir -p "$DOT_SAGE"
"$sage_root/venv/bin/python3" "$checker" --manifest "$manifest"
if [ "${1:-}" = --runtime-info ]; then
  test "$#" -eq 1
  exec "$sage_root/sage" -python "$checker" --manifest "$manifest" --probe
fi
exec "$sage_root/sage" "$@"
