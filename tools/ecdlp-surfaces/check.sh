#!/usr/bin/env bash
# Thin build and fixture-replay orchestration; all arithmetic runs in Rust.
set -euo pipefail
cd -- "$(dirname -- "$0")"

cargo fmt --all -- --check
cargo test --release --offline
cargo clippy --offline --all-targets -- -D warnings
cargo build --release --offline --bins

surface_fixture_dir=$(mktemp -d)
trap 'rm -rf -- "$surface_fixture_dir"' EXIT
cargo run --quiet --release --offline --bin surface_search -- \
  --output "$surface_fixture_dir/surface_candidates.json"
cargo run --quiet --release --offline --bin transfer_check -- \
  --scalar 37 --output "$surface_fixture_dir/transfer_certificate.json"
cargo run --quiet --release --offline --bin frobenius_filter -- \
  --output "$surface_fixture_dir/frobenius_result.json"
for surface_fixture in surface_candidates transfer_certificate frobenius_result; do
  cmp "examples/$surface_fixture.json" "$surface_fixture_dir/$surface_fixture.json"
done

# Public known-answer controls: a wrong witness and a composite field fail.
if cargo run --quiet --release --offline --bin transfer_check -- --scalar 38 \
  > "$surface_fixture_dir/invalid-witness.out" 2>&1; then
  echo 'incorrect scalar witness was accepted' >&2
  exit 1
fi
if cargo run --quiet --release --offline --bin surface_search -- --prime 15 \
  > "$surface_fixture_dir/composite-field.out" 2>&1; then
  echo 'composite field modulus was accepted' >&2
  exit 1
fi
echo 'Rust checks and committed example replay passed.'
