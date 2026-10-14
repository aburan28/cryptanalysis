#!/usr/bin/env bash
set -euo pipefail
cd /workspace/repos/crypto
n83_stamp=$(date -u +%Y%m%dT%H%MZ)
n83_study=research/ecdlp_surfaces_n83_20261012
n83_run="$n83_study/runs/run-$n83_stamp"
n83_report="$n83_study/reports/run-$n83_stamp"
test ! -e "$n83_run"
mkdir -p "$n83_run/identities" "$n83_report" "$n83_study/provenance"
date -u +%Y-%m-%dT%H:%M:%SZ > "$n83_run/start_utc.txt"
cargo build --release --offline --locked --manifest-path tools/ecdlp-surfaces/Cargo.toml --bins > "$n83_run/build.log" 2>&1
tools/ecdlp-surfaces/target/release/binary_surface_check --degree 83 --a both --output "$n83_run/n83.json" > "$n83_run/run.stdout.txt" 2> "$n83_run/run.stderr.txt"
for n83_a in 0 1; do
  n83_q=$(jq -r --argjson a "$n83_a" '.cases[] | select(.source.a==$a) | .source.Q | join(",")' "$n83_run/n83.json")
  tools/ecdlp-surfaces/target/release/binary_surface_check --a "$n83_a" --q-point "$n83_q" --output "$n83_run/no_witness_a$n83_a.json" > "$n83_run/no_witness_a$n83_a.stdout.txt" 2> "$n83_run/no_witness_a$n83_a.stderr.txt"
done

n83_error_control() {
  local n83_control=$1
  shift
  local n83_status=0
  tools/ecdlp-surfaces/target/release/binary_surface_check "$@" > "$n83_run/$n83_control.stdout.txt" 2> "$n83_run/$n83_control.stderr.txt" || n83_status=$?
  printf '%s\t%s\n' "$n83_control" "$n83_status" >> "$n83_run/control_exit_status.tsv"
  test "$n83_status" -eq 2
}
n83_error_control unsupported_degree --degree 82
n83_error_control two_torsion_a0 --a 0 --q-point 0,1
n83_error_control two_torsion_a1 --a 1 --q-point 0,1
n83_q0=$(jq -r '.cases[0].source.Q | join(",")' "$n83_run/n83.json")
n83_error_control wrong_witness --a 0 --q-point "$n83_q0" --scalar 38

cargo run --release --offline --locked --manifest-path docs/ecdlp-surfaces/certificates/Cargo.toml --bin binary_identities -- "$n83_run/n83.json" "$n83_run/identities" > "$n83_run/identities.log" 2>&1
cargo run --release --offline --locked --manifest-path docs/ecdlp-surfaces/certificates/Cargo.toml -- "$n83_run/old_identity_replay" > "$n83_run/old_identity_replay.log" 2>&1
for n83_old in embedding_identity quadric_determinant identity_replay curve_record; do
  cmp "docs/ecdlp-surfaces/evidence/$n83_old.json" "$n83_run/old_identity_replay/$n83_old.json"
done
tools/ecdlp-surfaces/check.sh > "$n83_run/package_checks.log" 2>&1
if cargo test --release --lib --locked > "$n83_run/root_library_gate.log" 2>&1; then
  printf '0\n' > "$n83_run/root_library_gate.exit.txt"
else
  printf '%s\n' "$?" > "$n83_run/root_library_gate.exit.txt"
fi
cp /workspace/output/n83-initial-check.json "$n83_run/initial_smoke.json"
git rev-parse HEAD > "$n83_run/producer_base_commit.txt"
uname -srm > "$n83_run/host.txt"
rustc --version > "$n83_run/rustc.txt"
sha256sum tools/ecdlp-surfaces/src/binary.rs tools/ecdlp-surfaces/src/bin/binary_surface_check.rs tools/ecdlp-surfaces/tests/binary.rs docs/ecdlp-surfaces/certificates/src/bin/binary_identities.rs tools/ecdlp-surfaces/target/release/binary_surface_check docs/ecdlp-surfaces/certificates/target/release/binary_identities > "$n83_run/source_and_binary.sha256"
date -u +%Y-%m-%dT%H:%M:%SZ > "$n83_run/end_utc.txt"
printf 'Recorded run: %s\nReport directory: %s\n' "$n83_run" "$n83_report"
