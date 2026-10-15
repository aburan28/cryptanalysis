#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export ELAN_TOOLCHAIN=$(cat "$here/lean-toolchain")
lean --version
lean "$here/BatchInverse.lean"
