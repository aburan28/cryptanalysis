# Pre-tau materialized mixed-radix tree

Moving the degree-three endomorphism into selected table entries lets the
fourteen-window mixed-radix 640 recoder use one absolute-gauge tree. On the
frozen 4,096-scalar panel, this changes the source-formula model from
552,976 to **516,096** field-kernel calls, saving 36,880 calls (nine per
scalar on average). The 64-case affine replay in `model.py` independently
checks the resulting points against binary scalar multiplication. This is
an operation model and correctness experiment; complete-operation timing is
still open. A native implementation in `native_variant.rs` builds both seed
images from the corresponding window bases and joins their selected affine
points through a balanced XYZZ tree. Its 64-scalar test passed against the
existing mixed-radix evaluator and independent binary multiplication;
source was then frozen at `3be9b655855595f41757ae3c18f1100129ffb0b6`
before drawing a disjoint 128-scalar panel. The fresh native replay matched
all 128 independently generated affine points and a separate native binary
scalar oracle. `holdout.json`, `holdout-native.log`, and `native-receipt.json`
bind that execution. A separate instrumented build checked each tree against
`10n-14` wrapper calls, recording exactly **16,128 calls** across the 128
cases (126 each); see `opcount-native.log` and `opcount-receipt.json`.
A paired diagnostic on those same 128 scalars counted **18,304** generic
field calls and **478** Solinas gauge rotations in the existing grouped
mixed-radix evaluator, versus **16,128** generic field calls and zero
rotations in the pre-tau tree. Both paths returned the same verified points.
The new tree saves 2,176 generic calls (17 per scalar) and 478 rotations in
these executed group-evaluation intervals. `pair-opcount-native.log` and
`pair-opcount-receipt.json` bind the diagnostic source and binary.

The prior mixed-radix atlas emits `(seed, exponent, unit)` with exponent in
`{0,1}`. For each window and seed that occurs with exponent 1, prepare the
point `tau(seed)` once. The lookup selects either `seed` or `tau(seed)`, then
applies the unit and inserts the point into the single tree. The identity

`tau(sum(unit_i(seed_i))) = sum(unit_i(tau(seed_i)))`

uses tau's group-homomorphism law and commutation with the six unit actions.
`TauMaterialization.lean` proves this implication for arbitrary point lists
under exactly those hypotheses. The proof does not yet instantiate the
secp256k1 point type or the Rust field arithmetic; this bridge remains a
formalization obligation. The pinned Lean receipt records the actual build
and `#print axioms` output. Native correctness does not establish a measured
speedup.

| Format | Distinct point slots | Point and atlas bytes | Modeled calls, 4,096 scalars |
| --- | ---: | ---: | ---: |
| Two tau buckets, compressed orbit | 415,190 | 44,588,220 | 552,976 |
| One tree, 64-byte tau entries | 808,296 | 69,747,004 | 534,629 |
| One tree with pre-tau entries | 808,296 | 82,326,396 | 516,096 |

The second table has 393,106 extra pre-tau entries, only for seed IDs actually
used at exponent 1. Its additional point payload is 37,738,176 bytes. The
table builder can form these entries from `tau(base)` for each window, using
the same seed multiples as the ordinary table; this needs one tau transform
per window base and a second table-building pass, rather than a tau transform
for every seed. Both passes and the compressed-orbit x preparation belong to
cold setup accounting. The middle row stores the extra tau points as ordinary
64-byte affine pairs and rotates their x-coordinate at selection when its
unit has a nonzero beta power. On the frozen panel, 18,533 tau terms require
that one-call rotation. It saves 18,347 calls against the two-bucket format
while using 12,579,392 fewer bytes than the fully compressed tau table. The
model charges 6/10/14 calls for affine/one-affine/projective tree joins, 14
for the two-bucket final projective join, and 6 multiplies plus 3 squares for
the old project's runtime tau map. It accounts for the four rare cases with
one leaf in the tau bucket. It excludes table construction, recoding,
affine recovery, memory traffic, and host wall time. The extra table can lose
on cache traffic despite its arithmetic saving.

The first native prototype retains a paired 192-byte record for **every**
seed slot. Its point and atlas payload is 84,446,460 bytes; it establishes
the recoder, prepared-tau point law, and join schedule, but does not yet
realize the sparse 82,326,396-byte table in the model. The pinned source
snapshot predates the canonical Solinas XYZZ backend, so this prototype
uses the existing Montgomery XYZZ formulas. `native_overlay.py` reconstructs
that source snapshot and applies the new code in a disposable crate. The
existing grouped native reference stores 64-byte points and has 31,302,140
point-plus-atlas bytes. The much larger candidate table makes a complete
cache-aware comparison essential before any runtime conclusion.

`native_hybrid64.py` changes the paired table to a 160-byte record: a
96-byte compressed ordinary point and a 64-byte affine tau point. A selected
tau point pays one Solinas rotation only when its unit has nonzero beta power.
The full-slot prototype has **71,160,380** point-plus-atlas bytes, while a
table containing tau points only for seed IDs that actually use exponent 1
would have 69,747,004 bytes. The first 128-case replay on the earlier holdout
passed as a calibration check. Hybrid source was frozen at
`f9371823b10ffb3b71c5c219e100d662028983f6`, then
`hybrid_holdout.py` drew a second disjoint 128-scalar panel. The native
evaluator matched all independently generated affine points and the separate
binary scalar oracle. Its actual retained table was **71,160,740 bytes**,
including metadata. On that panel an instrumented native build counted
**16,128** tree field calls and **601** selected-tau Solinas rotations,
exactly matching the independent integer-recoder model in
`hybrid-model.json`. The raw results and source/binary hashes are in
`hybrid64-holdout-native.log`, `hybrid64-native-receipt.json`,
`hybrid64-opcount-native.log`, and `hybrid64-opcount-receipt.json`.

The same 128-scalar hybrid holdout now has a native grouped-reference count:
**18,304 generic field calls and 477 Solinas rotations**, with every result
matching the independent affine oracle and binary multiplication. The hybrid
uses **16,128 generic tree calls and 601 selected-tau Solinas rotations** on
those same scalars. It saves 2,176 generic calls and spends 124 additional
rotations in the instrumented group-evaluation interval. The reference
instrumentation, executable hash, fixture hash, and raw output are retained
in `hybrid64-reference-opcount-receipt.json` and
`hybrid64-reference-opcount-native.log`. These counts do not establish which
implementation is faster: complete-operation accounting still needs recoding,
table lookup, memory traffic, and affine recovery. Table setup is separate
from this online operation count.

Compare the full operation on a host that passes the repository's isolated
benchmark preflight before making a CPU speed claim.

Reproduce the current receipts:

```sh
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/model.py
(cd experiments/prime-j0-mixed640-materialized-tree-20261013 && lean TauMaterialization.lean)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_overlay.py /private/tmp/mixed640-native-replay
(cd /private/tmp/mixed640-native-replay && cargo test --offline --locked --release --bin eisenstein_fixed fresh_64_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/holdout.py --check
(cd /private/tmp/mixed640-native-replay && MIXED640_HOLDOUT=/absolute/path/to/holdout.json cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_opcount.py /private/tmp/mixed640-opcount-replay
(cd /private/tmp/mixed640-opcount-replay && MIXED640_HOLDOUT=/absolute/path/to/holdout.json cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_pair_opcount.py /private/tmp/mixed640-pair-replay
(cd /private/tmp/mixed640-pair-replay && MIXED640_HOLDOUT=/absolute/path/to/holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-pair-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
(cd /private/tmp/mixed640-pair-replay && MIXED640_HOLDOUT=/absolute/path/to/hybrid-holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-pair-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/hybrid_holdout.py --check
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/hybrid_model.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_hybrid64.py /private/tmp/mixed640-hybrid64-replay
(cd /private/tmp/mixed640-hybrid64-replay && MIXED640_HOLDOUT=/absolute/path/to/hybrid-holdout.json cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_hybrid64_opcount.py /private/tmp/mixed640-hybrid64-opcount-replay
(cd /private/tmp/mixed640-hybrid64-opcount-replay && MIXED640_HOLDOUT=/absolute/path/to/hybrid-holdout.json cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
```
