#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
genus2_manifest=tools/binary-genus2-cover/Cargo.toml
cargo fmt --manifest-path "$genus2_manifest" --package binary-genus2-cover -- --check
cargo test --release --locked --manifest-path "$genus2_manifest"
cargo clippy --locked --manifest-path "$genus2_manifest" --package binary-genus2-cover --all-targets --no-deps -- -D warnings
genus2_run_dir=$(mktemp -d)
trap 'rm -rf -- "$genus2_run_dir"' EXIT
cargo run --release --locked --manifest-path "$genus2_manifest" --bin binary_genus2_check -- --a both --output "$genus2_run_dir/both.json"
jq -e '(.cases | length)==2 and all(.cases[]; .rD_P_zero and .rD_Q_zero and .inverse_P_roundtrip and .inverse_Q_roundtrip and .known_scalar_relation_verified) and all(.small_field_controls[]; .all_checks_passed)' "$genus2_run_dir/both.json" > /dev/null
cargo run --release --locked --manifest-path "$genus2_manifest" --bin binary_genus2_check -- --a 0 --q-point 0x590a9c0709b34b0bcd3d4,0x6aa49dc52796827db931a --output "$genus2_run_dir/unknown.json"
jq -e '.cases[0] | .scalar_mod_r==null and .known_scalar_relation_verified==null and .inverse_Q_roundtrip' "$genus2_run_dir/unknown.json" > /dev/null
cargo run --release --locked --manifest-path "$genus2_manifest" --bin genus2_identity -- "$genus2_run_dir/identities"
cmp research/binary_genus2_cover_20261014/runs/run-20261014T1442Z/identities/map_identity.json "$genus2_run_dir/identities/map_identity.json"
genus2_binary=$(cargo metadata --locked --manifest-path "$genus2_manifest" --format-version 1 --no-deps | jq -r '.target_directory + "/release/binary_genus2_check"')
for genus2_bad_args in '--a 2' '--unknown 1' '--a both --q-point O' '--a 0 --q-point 0x0,0x0' '--a 0 --scalar -1' '--a 0 --q-point 0x590a9c0709b34b0bcd3d4,0x6aa49dc52796827db931a --scalar 38'; do
  # Intentional word splitting: fixed literal argument vectors above.
  if "$genus2_binary" $genus2_bad_args > "$genus2_run_dir/negative.stdout" 2> "$genus2_run_dir/negative.stderr"; then
    printf 'invalid CLI input accepted: %s\n' "$genus2_bad_args" >&2
    exit 1
  else
    genus2_status=$?
    test "$genus2_status" -eq 2
    printf 'Rejected with exit 2: %s\n' "$genus2_bad_args"
    cat "$genus2_run_dir/negative.stderr"
  fi
done
