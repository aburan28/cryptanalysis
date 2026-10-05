#!/usr/bin/env bash
set -euo pipefail

# Thin native build/replay orchestration. No timings or comparison are emitted.
QUARTIC_REPO=$(cd -- "$(dirname -- "$0")/.." && pwd)
QUARTIC_CRATE="$QUARTIC_REPO"
if [[ -d "$QUARTIC_REPO/suite/src/cryptanalysis" ]]; then
  QUARTIC_CRATE="$QUARTIC_REPO/suite"
fi
QUARTIC_RUSTC=${QUARTIC_RUSTC:-rustc}
QUARTIC_RUSTFMT=${QUARTIC_RUSTFMT:-rustfmt}
QUARTIC_TMP=$(mktemp -d)
trap 'rm -rf -- "$QUARTIC_TMP"' EXIT

"$QUARTIC_RUSTFMT" --edition 2021 --check --config skip_children=true \
  "$QUARTIC_CRATE/src/cryptanalysis/bielliptic_quartic.rs" \
  "$QUARTIC_CRATE/src/bin/quartic_ic.rs"
"$QUARTIC_RUSTC" --edition 2021 -D warnings --test \
  "$QUARTIC_CRATE/src/cryptanalysis/bielliptic_quartic.rs" -o "$QUARTIC_TMP/tests"
"$QUARTIC_TMP/tests" --test-threads=1
"$QUARTIC_RUSTC" --edition 2021 -D warnings \
  "$QUARTIC_CRATE/src/bin/quartic_ic.rs" -o "$QUARTIC_TMP/quartic-ic"
node "$QUARTIC_REPO/tools/check_bielliptic_quartic.mjs" \
  "$QUARTIC_TMP/quartic-ic" "$QUARTIC_CRATE"
