#!/usr/bin/env bash
set -euo pipefail

# exp-run holds the serial lock before starting this script.
source_root=${BENCH_SOURCE_ROOT:?BENCH_SOURCE_ROOT must name frozen source}
stage_root=${BENCH_STAGE_ROOT:?BENCH_STAGE_ROOT must name frozen stage}
cd "$stage_root"
sha256sum -c source-files.sha256 > source-integrity-before.log
printf 'source_index_sha256='; sha256sum source-files.sha256

cd "$source_root"
uname -a
rustc --version
cargo --version
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
"$binary" --check-scalar-unit-orbit-u256-sector15-fixed-fixture "$fixture"
"$binary" --check-scalar-unit-orbit-u256-radix384-fixed-fixture "$fixture"

cd "$stage_root"
sha256sum -c source-files.sha256 > source-integrity-after.log
printf 'source_integrity=passed files='; wc -l < source-files.sha256

# Probe is diagnostic on a container; retain its status without letting a
# failed host-level isolation gate erase a completed correctness replay.
set +e
python3 "$source_root/scripts/isolated_bench.py" probe-host > host-probe.stdout 2> host-probe.stderr
probe_exit=$?
set -e
printf '%s\n' "$probe_exit" > host-probe.exit
printf 'host_probe_exit=%s\n' "$probe_exit"
