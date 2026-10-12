# Native radix-569 bounded top-ball replay

The opt-in Rust evaluator builds **756,033 affine point entries** and
returns the expected secp256k1 public point for all 512 scalars in the
disjoint holdout. Its exact native atlas audit checks every one of the
327,235 admissible top states and its rank, while the ordinary atlas
and terminal atlas byte streams match separately frozen Python SHA-256
digests. The native point stream matches the independent group replay.

| Native replay measure | Result |
| --- | ---: |
| Ordinary residues audited by the design replay | 323,761 |
| Native terminal states and unit ranks checked | 327,235 |
| Holdout public points matched | 512 / 512 |
| Affine point entries | 756,033 |
| Affine point payload at 64 bytes each | 48,386,112 bytes |
| Complete retained bytes on the local ARM64 build | **49,929,614 bytes** |
| Final point additions across the holdout | 6,656 |
| Gauge rotations across the holdout | 1,248 |

The complete retained count includes point entries, ordinary residue codes,
canonical digits, terminal row prefixes and lower bounds, unit constants,
Pareto plans, and table containers. It is 14,413,154 bytes below the
recorded format-173 native table and 19,056,474 bytes below the native
radix-671 split-top table. The 4,096-scalar design source model differs
from split-top by 528 products on matched inputs; the 512-scalar holdout
has a separate input seed.

[`native-replay.json`](native-replay.json) binds the portable semantic
result to source, atlas, plan, fixture, and point-stream hashes.
[`native-rows.jsonl`](native-rows.jsonl) retains every point, addition,
and rotation count. [`native-local-build.json`](native-local-build.json)
records the local architecture, Rust version, executable hash, and retained
bytes. The overlay is included into a disposable copy of the shared native
crate, leaving its current production routing under its existing owner.

From the repository root, with the locked Cargo dependencies cached:

```sh
export CARGO_TARGET_DIR=/private/tmp/radix569-native-target
python3 experiments/prime-j0-radix569-topball-20261012/native_overlay.py \
  /private/tmp/radix569-native-overlay --build
python3 experiments/prime-j0-radix569-topball-20261012/native_replay.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --overlay-record /private/tmp/radix569-native-overlay/overlay.json --check
```

The disposable binary accepts `--radix569-case FIXTURE INDEX` to replay one
public point. It warms reusable tables before timing scalar recoding,
lookup, group combination, and point comparison. A paired CPU comparison
requires the isolated host receipt, the same public input, and the same
resource envelope for both formats. The local run verifies complete
operations and retained memory.
