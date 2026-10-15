#!/usr/bin/env bash
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
experiments=$(cd "$here/.." && pwd)
export ELAN_TOOLCHAIN=leanprover/lean4:v4.34.1
build_dir=$(mktemp -d /private/tmp/lean268.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

version=$(lean --version)
case "$version" in
  *"Lean (version 4.34.1"*) ;;
  *) echo "Expected Lean 4.34.1, got: $version" >&2; exit 1 ;;
esac
printf '%s\n' "$version"

build() {
  local source=$1
  local name=${source##*/}
  name=${name%.lean}
  printf 'Checking %s\n' "$name"
  LEAN_PATH="$build_dir" lean -o "$build_dir/$name.olean" "$experiments/$source"
}

build prime-j0-mixed640-materialized-tree-20261013/SplitPrimeRadix.lean
build prime-j0-mixed640-materialized-tree-20261013/SplitPrimeLatticeCell.lean
build prime-j0-mixed640-materialized-tree-20261013/SplitPrimeNormBound.lean
build prime-j0-nearest-digit-12211-20261014/SplitPrime12211NearestBound.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Bound.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Selector.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Digits.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Step.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Complete.lean
build prime-j0-fifteen-position-radix-20261015/NearestOrbit71023Tie.lean
