# N83 packed-root collision audit

The 29.9-million-state packed S₃ index contains **294 duplicate canonical
root records, all explained by pair symmetry**. Independent Sage replay
checked all 588 collision witnesses against the frozen state permutation,
representative coordinates, curve lifts, and S₃ polynomial. Of the 294
groups, 292 swap the two indexed x coordinates and two repeat the two root
selectors of one equal-input state. The resulting nontrivial relation count
and novel rank increment are both **zero** for this sampled index.

| Frozen scope | Value |
| --- | ---: |
| Curve | `EC1N83Ckb1h876c2921cb64` |
| Exact usable factor-base points before folding, `B` | 30,977,592 |
| Folded columns, `K` | 186,612 |
| Ordered pair states sampled | 29,900,000 |
| Satisfiable S₃ states | 29,900,000 |
| Packed root records | 59,800,000 |
| Distinct canonical root keys | 59,799,706 |
| Duplicate-key groups | 294 |
| Swapped pair groups | 292 |
| Same-state two-selector groups | 2 |
| Distinct unordered-pair groups | 0 |
| Novel relation rank from these groups | 0 |

The [raw audit](collision_audit_29900000.json) retains every duplicate key,
both descriptors, state offsets, Frobenius shifts, and the aligned polynomial
x coordinates. The [Sage replay](independent_sage_replay.json) checks the
producer output from the [pinned manifest](stage_manifest.json),
[source](native_packed_index.rs), and independent field implementation. The
[protocol](protocol.json) hashes the inputs, executable, and evidence. The
native index build and sort took 18.659 seconds and peaked at 2,905,849,856
RSS bytes on the local shared host; those times are exploratory. This audit
stops after target-independent index construction and does not contribute an
online target measurement.

## Why the collisions give zero rows

The index samples ordered states `(left, right, relative_power)` and stores
both roots of each S₃ quadratic. Since S₃ is symmetric in its first two
inputs, sampling the reversed state can reproduce a canonical root with the
same unordered pair of base x coordinates. When the inputs coincide, the two
root selectors can also encode the same root. The Sage replay classified
every reported duplicate through the aligned polynomial coordinates, then
verified the curve lift and the S₃ equation
`(xy+xz+yz)^2 + xyz + 1 = 0` in `GF(2^83)`.

For two identical ordered point pairs, their difference is zero. For reversed
pairs, `(P+Q)−(Q+P)=0`. These are the only reported collision classes, so
their anchor-difference rows are zero. The conditional group cancellations
are checked in [CollisionCancellation.lean](CollisionCancellation.lean):
`same_pair_cancels` assumes self-cancellation, and `swapped_pair_cancels`
assumes commutativity and self-cancellation. [Lean build output](lean-build.txt)
contains the `#print axioms` audit; both declarations use no axioms. The
specific N83 field, curve, S₃ root index, and witness classification are
checked computationally by the pinned native run and independent Sage replay;
their bridge to the generic Lean group laws is not formalized here.

The count `59,800,000 − 59,799,706 = 294` is an upper bound on independent
anchor-difference rows even before classification: a group with `m` records
has at most `m−1` anchor differences. The classification tightens the observed
increment to zero. This is a result for the frozen 29.9-million-state sample;
it does not extrapolate a collision rate to a larger or differently sampled
index.

## Reproduce

From this experiment directory, using an SSD-backed Cargo target directory:

```sh
python3 restore_crypto_source.py
NATIVE_S3_SOURCE_SHA256=$(shasum -a 256 native_packed_index.rs | awk '{print $1}') \
NATIVE_S3_BUILD_MANIFEST_SHA256=$(shasum -a 256 Cargo.toml | awk '{print $1}') \
CARGO_TARGET_DIR=/Volumes/SSD990/llm/tmp/n83-e3-cargo-target \
cargo build --release --locked --offline
```

Then run:

```sh
N83_COLLISION_AUDIT=1 /Volumes/SSD990/llm/tmp/n83-e3-cargo-target/release/native_packed_index \
  stage_manifest.json ../adaptive_all_orientations_20261004/inputs/n83_onb_poly_bridge.json \
  ../adaptive_all_orientations_20261004/inputs/n83_x_representatives.bin \
  29900000 5500 packed_sparse30_rank16_cachedxy /private/tmp/n83-e3-replay-raw.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /private/tmp/n83-e3-replay-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python verify_sage.py \
  --raw /private/tmp/n83-e3-replay-raw.json --output /private/tmp/n83-e3-replay-sage.json
lean CollisionCancellation.lean
python3 verify_receipt.py \
  --binary /Volumes/SSD990/llm/tmp/n83-e3-cargo-target/release/native_packed_index
```

Choose unused paths for the new replay files. `verify_receipt.py` checks the
published source, input, binary, and evidence hashes; the Sage verifier checks
all published or newly produced collision witnesses. The checked local Sage
launcher is required for the Sage replay, and the pinned [toolchain](lean-toolchain)
is required for the Lean proof.

The next factor-base experiment should obtain ordinary-query relations and
novel rank for a five-summand base on the same public point. Reusing these
pair-root self-collisions cannot supply the missing rank for this sampled
index.
