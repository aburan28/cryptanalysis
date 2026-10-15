#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export ELAN_TOOLCHAIN=$(cat "$here/lean-toolchain")
proof_tmp=$(mktemp -d)
trap 'rm -rf "$proof_tmp"' EXIT
lean --version
lean -o "$proof_tmp/UnitClasses.olean" "$here/UnitClasses.lean"
