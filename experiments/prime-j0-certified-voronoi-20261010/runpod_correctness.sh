#!/usr/bin/env bash
set -euo pipefail

# Run inside the serial exp-run queue. The caller unpacks the frozen source
# archive into BENCH_SOURCE_ROOT before this script starts.
source_root=${BENCH_SOURCE_ROOT:?BENCH_SOURCE_ROOT must name the frozen source tree}
cd "$source_root"

find experiments -type f -print0 | sort -z | xargs -0 sha256sum > source-files.sha256
sha256sum source-files.sha256
uname -a
rustc --version
cargo --version

export CARGO_TARGET_DIR="$source_root/target"
cargo test --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed -- --test-threads=2

cargo build --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary"
fixture=experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json
"$binary" --check-scalar-unit-orbit-reciprocal-fixed-fixture "$fixture"
"$binary" --check-scalar-unit-orbit-certified-fixed-fixture "$fixture"
