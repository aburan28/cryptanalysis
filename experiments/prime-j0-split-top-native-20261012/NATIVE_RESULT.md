# Native radix-671 split-top replay

The opt-in Rust evaluator builds 1,044,625 affine secp256k1 point entries
and returns the frozen public point for every scalar in the independent
512-case holdout. It audited all 450,241 ordinary radix residues, checked
every low and high rectangle rank, and matched the three separately frozen
atlas byte streams. The final point-stream SHA-256 is
`c6e43ec4d2d9dfd0efba21a1d208c55aa2de6413451e19e1b19af36053e7d9b3`.

| Native replay measure | Result |
| --- | ---: |
| Ordinary residues audited | 450,241 |
| Low and high rectangle entries | 65,536 and 78,597 |
| Holdout public points matched | 512 / 512 |
| Affine point entries | 1,044,625 |
| Affine point payload at 64 bytes each | 66,856,000 bytes |
| Complete retained bytes on the local ARM64 build | 68,986,088 bytes |
| Final point additions across the 512 cases | 6,656 |
| Gauge rotations across the 512 cases | 1,195 |

The retained count includes point entries, residue codes, canonical digits,
unit constants, Pareto plans, and table containers. The byte count is
54,313,590 below the native radix-929 top-ball build's recorded 123,299,678
bytes, using the same 64-byte affine representation and local ARM64 toolchain.
The 512-case scalar panels have different seeds, so the per-panel operation
counts are diagnostics for their own frozen inputs, not a paired timing
comparison.

[`native-replay.json`](native-replay.json) binds the portable semantic
result to source, input, and point-stream hashes.
[`native-rows.jsonl`](native-rows.jsonl) retains the exact point, additions,
and rotations for each case. [`native-local-build.json`](native-local-build.json)
records the local Rust version, architecture, binary hash, and complete
retained byte count.

The code is included into a disposable copy of the shared native crate.
`native_overlay.py` checks the insertion point and source hashes, while
`native_replay.py` checks the compiled source, atlases, and all 512 point
outputs. The shared production source and its routing are unchanged.

From the repository root, with the locked Cargo dependencies cached:

```sh
export CARGO_TARGET_DIR=/private/tmp/split671-native-target
python3 experiments/prime-j0-split-top-native-20261012/native_overlay.py \
  /private/tmp/split671-native-overlay --build
python3 experiments/prime-j0-split-top-native-20261012/native_replay.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --overlay-record /private/tmp/split671-native-overlay/overlay.json --check
```

The disposable binary accepts `--split671-case FIXTURE INDEX` for a single
public-point replay. It warms reusable tables before the interval, then times
scalar recoding, lookup, group combination, and point comparison. A future
paired format run needs an isolated host receipt and identical frozen inputs.
This local build establishes complete-operation correctness and memory size.
