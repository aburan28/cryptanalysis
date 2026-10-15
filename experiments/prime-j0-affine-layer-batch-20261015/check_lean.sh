#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
parent="$here/../prime-j0-xyzz-batch-inversion-20261015"
export ELAN_TOOLCHAIN=$(cat "$here/lean-toolchain")
proof_tmp=$(mktemp -d)
trap 'rm -rf "$proof_tmp"' EXIT
lean --version
lean -o "$proof_tmp/BatchInverse.olean" "$parent/BatchInverse.lean"
lean -o "$proof_tmp/AffineLayer.olean" "$here/AffineLayer.lean"
