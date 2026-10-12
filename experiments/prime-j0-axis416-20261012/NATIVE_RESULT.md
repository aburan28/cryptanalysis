# Native axis-factorized radix-416 replay

The opt-in Rust evaluator builds 433,578 stored point entries and returns
the expected secp256k1 public point for all 512 scalars in the disjoint
holdout. Its complete retained table is **28,557,008 bytes** on the local
ARM64 build, including point payload, ordinary residue codes, canonical
digits, table containers, and unit constants.

| Native replay measure | Result |
| --- | ---: |
| Ordinary residues audited | 173,056 |
| Canonical orbit digits | 28,844 |
| Stored point entries | 433,578 |
| Point payload at 64 bytes each | 27,748,992 bytes |
| Complete retained bytes | **28,557,008 bytes** |
| Holdout public points matched | **512 / 512** |
| Point additions across holdout | 7,168 |
| Gauge rotations across holdout | 1,020 |

The native ordinary atlas byte stream matches the separately frozen
Python digest. The native public-point stream matches the independent
affine group replay digest
`0c1273d82e3f810444bd004a0fe16115d620115cb2f2538f85b6a6c46dd6ac82`.
The executable uses a 15-term sequential gauge accumulator; the prior
radix-569 implementation uses a fourteen-term Pareto tree. These counts
describe their exact implementations. CPU wall-time ranking requires
paired complete operations on an isolated host.

`native-replay.json` binds source, atlas, fixture, and per-case point hashes.
`native-rows.jsonl` records every final point, addition, and rotation count.
`native-local-build.json` records the architecture, Rust version, binary
hash, overlay record, and complete retained bytes. The overlay builds a
disposable copy of the shared native crate; it does not edit or route
production arithmetic.

From the repository root, with locked Cargo dependencies cached:

```sh
export CARGO_TARGET_DIR=/private/tmp/axis416-native-target
python3 experiments/prime-j0-axis416-20261012/native_overlay.py \
  /private/tmp/axis416-native-overlay --build
python3 experiments/prime-j0-axis416-20261012/native_replay.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --overlay-record /private/tmp/axis416-native-overlay/overlay.json --check
```
