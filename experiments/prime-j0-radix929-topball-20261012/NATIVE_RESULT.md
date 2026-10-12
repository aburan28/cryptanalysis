# Native radix-929 bounded top-state replay

The opt-in Rust implementation builds all 1,863,085 affine point entries,
indexes the bounded top table with a 953-row arithmetic prefix, and returns
the expected secp256k1 point for every scalar in the independent 512-case
holdout. Its native atlas audit checks each of the 821,953 admissible top
states against the exact orbit rank and unit code. The final point digest is
`38461b6e1a8b75bbb10c05ce54ed90b3fae9641039536d9473dd6b393ab75127`,
matching the frozen independent replay. The native ordinary atlas and top
atlas byte streams also match the separately frozen Python SHA-256 digests.

| Native replay measure | Result |
| --- | ---: |
| Top states and orbit ranks checked | 821,953 states / 136,993 orbits |
| Native atlas order matched to frozen digests | 143,841 ordinary + 136,992 nonzero top entries |
| Holdout public points matched | 512 / 512 |
| Affine point entries | 1,863,085 |
| Affine point payload at 64 bytes each | 119,237,440 bytes |
| Full retained bytes on the local ARM64 build | 123,299,678 bytes |
| Final point additions in the 512-case panel | 6,144 |
| Gauge rotations in the 512-case panel | 1,129 |

The full retained count includes point entries, radix residue codes,
canonical digits, top row prefixes/lower bounds, unit constants, and the
Pareto plan. [`native-local-build.json`](native-local-build.json) records the
physical build's Rust version, architecture and binary hash;
[`native-replay.json`](native-replay.json) binds the portable semantic result
to source and input hashes. [`native-rows.jsonl`](native-rows.jsonl) retains
every case's point, addition count and rotation count.

The implementation is an overlay included into a **disposable copy** of the
existing native crate. `native_overlay.py` checks one exact insertion point,
copies the crate under a chosen temporary directory, adds the two Rust
modules, and builds with the locked dependencies. The shared source remains
available to its current Conductor owner. This is a complete native
correctness prototype; the code is opt-in and has no automatic routing.

From this repository root, with the locked Cargo dependencies cached:

```sh
export CARGO_TARGET_DIR=/private/tmp/radix929-native-target
python3 experiments/prime-j0-radix929-topball-20261012/native_overlay.py \
  /private/tmp/radix929-native-overlay --build
python3 experiments/prime-j0-radix929-topball-20261012/native_replay.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --overlay-record /private/tmp/radix929-native-overlay/overlay.json --check
```

The disposable binary also accepts `--radix929-case FIXTURE INDEX`. It warms
the reusable table before the interval, then times scalar recoding, lookup,
point combination, and comparison with the independently supplied point.
Its `verified=1 online_ms=...` output is suitable for the serial isolated
benchmark service once the host preflight passes. This local ARM64 run was
used for exact point and memory checks; no CPU speed ratio is inferred.
The paired format-174 workload and host-specific manifest commands are in
[`ISOLATED_PANEL.md`](ISOLATED_PANEL.md).
