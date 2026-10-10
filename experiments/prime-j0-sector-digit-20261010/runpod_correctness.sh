#!/usr/bin/env bash
set -euo pipefail

# The exp-run service holds the global serial lock before invoking this file.
source_root=${BENCH_SOURCE_ROOT:?BENCH_SOURCE_ROOT must name frozen source}
stage_root=${BENCH_STAGE_ROOT:?BENCH_STAGE_ROOT must name frozen stage}
cd "$stage_root"
sha256sum -c source-files.sha256 > source-integrity-before.log
printf 'source_index_sha256='; sha256sum source-files.sha256

cd "$source_root"
uname -a
rustc --version
cargo --version
python3 experiments/prime-j0-sector-digit-20261010/check_algebra.py
export CARGO_TARGET_DIR="$stage_root/target"
cargo test --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed -- --test-threads=2
cargo build --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary"
fixture=experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json
"$binary" --check-scalar-unit-orbit-u256-formula-fixed-fixture "$fixture"
"$binary" --check-scalar-unit-orbit-u256-sector-fixed-fixture "$fixture"

cd "$stage_root"
sha256sum -c source-files.sha256 > source-integrity-after.log
printf 'source_integrity=passed files='; wc -l < source-files.sha256
