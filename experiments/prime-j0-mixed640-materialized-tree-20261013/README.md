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
| One tree, 64-byte ordinary and tau entries | 808,296 | 56,460,924 | 554,411 |
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

`native_affine128.py` stores both the ordinary point and its prepared tau
image as 64-byte affine coordinates. This 128-byte pair removes the third
coordinate from each ordinary point and rotates either selected point's
x-coordinate with the Solinas constant when its unit requires beta or
beta-squared. The full-slot native table retains **57,874,660 bytes**
including metadata, 13,286,080 fewer than the 160-byte hybrid. After source
freeze at `913a5c27ee13548ed510c9ead6b3b8f01bb497b0`, a third disjoint
128-scalar holdout matched every independently generated affine point and
native binary multiplication. Its independent recoder model and native
instrumentation both counted **16,128** tree calls and **1,212** selected-unit
Solinas rotations. The grouped reference on those same scalars used **18,304**
generic calls and **469** rotations. Thus the 128-byte format saves 2,176
generic calls while adding 743 rotations in the counted interval. The
fixture, source and binary hashes, raw logs, and the three native receipts
are retained as `affine-holdout.json`, `affine-model.json`, and the
`affine128-*` files. On the frozen 4,096-scalar panel, the source-formula
model counts 516,096 tree calls and 38,315 selected-unit rotations, or
554,411 calls when each rotation is counted once. That equal-call total is
1,435 above the two-bucket model. The compact table is a memory candidate,
and its wall time and complete-operation cost are still unmeasured.

## Fixed orbit-gauge experiment

A 128-byte pair can store each point in a chosen beta orbit gauge `g` and
select the unit power `(u-g) mod 3`. The identity
`beta^(u-g)(beta^g P) = beta^u P` is formalized as `gauge_shift` in
`GaugeShift.lean`, with the three-cycle action law stated explicitly. The
pinned Lean receipt records a successful build and `#print axioms` output;
connecting that abstract action to the Rust field and curve implementation
remains open. The native version uses a fixed gauge for each of the fourteen
windows and each tau exponent, so it stores no per-point gauge metadata.

`gauge_policy.py` chose these 28 gauges solely from the older 4,096-scalar
panel, then the policy, implementation, instrumentation, and proof were
frozen at `f05eb12cd4d490a4aaa1c60b1d3ad96d95c73814`. Training predicted
38,315 rotations without gauges and 37,723 with them. A subsequent disjoint
128-scalar holdout verified every affine point and binary scalar result, but
its paired native counters were **1,228 rotations without gauges and 1,249
with gauges**, with **16,128 tree calls** for either format. The frozen policy
therefore lost 21 rotations on that holdout. `gauge-holdout.json`,
`gauge-test-model.json`, and the `gauge128-*-receipt.json` files bind these
results to source, binary, fixture, and raw output hashes.

A separate deterministic 65,536-scalar model replay, disjoint from the
training and native panels, counted 611,926 ungauged versus 610,209 gauged
rotations. The paired mean saving is 0.0262 rotations per scalar, with a
normal-approximation 95% interval of 0.00695–0.04545 under that input law.
This replication evaluates recoder choices only; it does not replay those
65,536 points in the native evaluator. The first fixed-gauge builder rotates each
gauged table entry, requiring 560,029 additional setup rotations under the
fixed policy. At the model replay's mean saving, those rotations alone need
about 21.4 million scalar evaluations to amortize. Runtime gauge selection
and memory traffic remain uncharged. `gauge-replication.json` records the
fixed seed, input law, scalar-stream hash, paired counts, and uncertainty.

An exhaustive scan of all three atlas codebooks found equal counts for
beta powers 0, 1, and 2 within every nonidentity `(seed, exponent)` group.
Thus per-seed gauge choice has zero rotation advantage under a uniform atlas
residue law. `gauge-atlas-audit.json` retains the exact codebook counts and
hashes. The window-level signal arises from the declared scalar recoder law,
and its small size makes table-construction and selection cost decisive.

The native_gauge128_base.py variant moves each stored gauge to its window
base before building the table. Because the beta action is a group
homomorphism and commutes with tau, the builder then produces the same
gauged points without rotating every entry. The frozen source calls the
Jacobian omega map 27 times across the 28 base channels and removes the
560,029 per-entry Solinas rotations counted above. This is source-level
setup-operation accounting; complete table-build timing is still open. The
proof obligations are the homomorphism and commutation hypotheses in
TauMaterialization.tau_unit_fold and the unit-adjustment identity in
GaugeShift.gauge_shift; a concrete Lean curve instance remains open.

The base-rotated source was frozen at
0db3af3443f405f6f2f626df23ca950ae1953d4b after 128 prior-panel points
passed independent affine and binary checks. A fifth disjoint 128-scalar
panel then verified all points. Native instrumentation matched the
independent model: **16,128 tree calls and 1,184 selected-unit rotations**
for the base-rotated gauge, versus **16,128 calls and 1,207 rotations** for
the ungauged 128-byte table on those same scalars. Both retained 57,874,660
bytes including metadata. The fixed policy therefore saved 23 rotations on
this panel; the earlier gauge panel lost 21, so neither panel alone supports
a general speed assertion. The base-holdout.json, base-test-model.json, and
gaugebase128 receipt files preserve the paired evidence.

## Selective orbit compression under a 64 MiB table cap

The new table stores each window and tau channel uniformly as either 64-byte
affine points or 96-byte compressed orbit points. The compressed form carries
the prepared x coordinate needed to apply beta powers during selection, so
it avoids a selected-unit Solinas rotation in that channel. Channel-level
tags avoid per-point dispatch metadata. The frozen 4,096-scalar training
panel supplied one rotation count and one table cost for each of the 28
channels. `selective_policy.py` chose the channel subset by exact
meet-in-the-middle integer optimization under a 64 MiB retained-table cap;
`selective_optimality_check.py` independently checked the optimum with a
capacity-indexed dynamic program. The selected 12 channels contain 285,480
point slots. They remove 17,264 of the training panel's 38,315 affine
selection rotations while keeping modeled point-and-atlas bytes at
67,009,660. The native retained table is 67,010,468 bytes, including 808
metadata bytes, and has 98,396 bytes of headroom below the cap.

The policy and native evaluator were frozen at
`63d4059b28693951ae3e7cd9beb0d6e2410972f7` before drawing
`selective-holdout.json`, a disjoint 128-scalar panel. Three instrumented
native builds returned the same 128 independently checked affine and binary
scalar results. The integer recoder model predicted every count below.

| Paired format on selective holdout | Retained bytes | Tree generic calls | Selected-unit Solinas rotations |
| --- | ---: | ---: | ---: |
| All affine, 128-byte pair | 57,874,660 | 16,128 | 1,209 |
| Selective compressed channels, up to 64 MiB | 67,010,468 | 16,128 | 674 |
| Hybrid, 160-byte pair | 71,160,740 | 16,128 | 577 |

Selective compression saves 535 rotations relative to all affine for
9,135,808 more retained bytes. Relative to the 160-byte hybrid, it saves
4,150,272 retained bytes at a cost of 97 rotations. Table preparation
converts 285,480 entries to the compressed form; those conversions,
recoding, lookup traffic, affine recovery, and cache effects require a
complete-operation measurement. These are verified operation counts and
memory sizes, with no isolated wall-time ratio. The three raw logs and
`selective64-*-receipt.json` files bind the source, generated module,
binary, fixture, policy, model, and results.

Compare the full operation on a host that passes the repository's isolated
benchmark preflight before making a CPU speed claim. A RunPod CPU Pod can
qualify only for the separate instance-scoped Tier 1 gate when its paired
noise and correctness checks pass; it does not establish host exclusivity.

### RunPod Tier 1 full-operation timing, 2026-10-13

The serial isolated-benchmark service ran one A/A affine control and one
affine-reference/selective-candidate comparison on RunPod instance
`rrao2y0m5xlahr`. Each used eight alternating-order pairs for the same
frozen holdout point (`selective_holdout_case_0`), CPU 14, NUMA node 0,
and the same online timing boundary: start immediately before the
scalar-dependent pre-tau multiplication call and stop after affine point
recovery. Recoding, lookup, selection, tree evaluation, and recovery are
included. Table preparation and fixture loading are outside that interval;
each invocation records its table preparation time separately. The runner
verified the output point and required fixture fields on every invocation.

| Panel | Valid pairs | Median affine/reference divided by candidate online time | Paired bootstrap 95% interval | Median table preparation, reference/candidate |
| --- | ---: | ---: | ---: | ---: |
| Affine A/A control | 8/8 | 0.9803 | 0.9490–1.0531 | 9,728/9,700 ms |
| Affine versus selective | 8/8 | 1.0294 | 0.9720–1.1259 | 10,441/10,491 ms |

All 32 invocations were valid, with stable artifact, runner, and binary
hashes. The recorded cgroup throttle and per-CPU steal deltas were zero.
The A/B interval includes 1 and overlaps the A/A noise range, so this
panel does not resolve an online timing advantage. This is an
instance-scoped Tier 1 measurement: the preflight passed, but the Pod does
not prove host-exclusive CPU ownership. Only one frozen scalar was timed,
with one multiplication per process and 0.066–0.082 ms online intervals;
a longer, multi-case paired panel or host-exclusive repeat is the next
timing gate. The observed A/B median is a diagnostic, not a qualified
speedup ratio.

The complete [Tier 1 receipts](tier1-runpod-20261013/) preserve both
manifests, preflights, per-invocation counters and outputs, paired rows,
and summaries. The A/A and A/B job IDs are
`71c10fc08f214c37b805653d0cf28808` and
`c917dc6bee7046e9b780df17d158d921`. Their result archives were
transferred from the Pod and SHA-256-checked before extraction. The
runner hash is `48361f0d0a5138e9e2f1264ff3de689fddb9d1a5181afd089e70c153e3a089cc`;
the allocation receipt hash is
`f9887f1b1cb100abd598709195f4061fbbe050ebf51bfbcc7c95788defa48d70`.
Use `native_bench_cli.py` to generate the pinned benchmark front doors and
`make_tier1_manifest.py` to create a manifest for a new case or panel.

### Fixed-capacity tree and adjacent-pair cache screen

`native_stack_tree.py` keeps the selective table and the exact pairwise
reduction order while replacing per-level `Vec` allocations with a
14-slot stack array. The generated evaluator passed the 128-scalar frozen
holdout against the independent affine fixture and binary multiplication on
the Linux Pod. Its one-case Tier 1 panel used the same scalar and the
selective vector evaluator as reference:

| Panel | Valid pairs | Median vector/stack online ratio | Paired bootstrap 95% interval | Median table preparation, vector/stack |
| --- | ---: | ---: | ---: | ---: |
| Selective vector versus stack tree | 8/8 | 1.0440 | 0.9213–1.0908 | 10,392/10,402 ms |

All 16 invocations were valid with stable source, runner, and binary
hashes. The interval includes 1 and overlaps the affine A/A noise band,
so the allocation change has unresolved latency effect here. The raw
receipt is job `bc5733ccc4be4b3f84df257d53f5c789` in the
[Tier 1 directory](tier1-runpod-20261013/). Its archive SHA-256 was
`ff8c5061649baa42e5f30ddc770e12c3dcdc507790b802f517e49a0c7459ff25`
before extraction.

`pair_reuse_screen.py` tested a separate format idea: precompute exact sums
of selected points in adjacent window pairs, then cache those sums under a
fixed entry budget. The first 2,048 scalars of the frozen 4,096-scalar
panel supplied 14,336 distinct pair keys. Caching even all 14,336 of
them produced **zero hits** in the other 2,048 scalars (14,336 pair slots)
and in the disjoint 128-scalar holdout (896 pair slots). Thus this exact
pair-key cache does not transfer under these input laws; a useful pair
scheme would need algebraic sharing or a coarser reusable key. The
[screen receipt](pair-reuse-screen.json) includes input and atlas hashes,
the tested budgets, and zero-seed counts. Recompute it with
`python3 pair_reuse_screen.py` from this directory.

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
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/affine_holdout.py --check
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/affine_model.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_affine128.py /private/tmp/mixed640-affine128-replay
(cd /private/tmp/mixed640-affine128-replay && MIXED640_HOLDOUT=/absolute/path/to/affine-holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-affine128-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_affine128_opcount.py /private/tmp/mixed640-affine128-opcount-replay
(cd /private/tmp/mixed640-affine128-opcount-replay && MIXED640_HOLDOUT=/absolute/path/to/affine-holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-affine128-opcount-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/gauge_policy.py
(cd experiments/prime-j0-mixed640-materialized-tree-20261013 && lean GaugeShift.lean)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/gauge_holdout.py --check
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/gauge_test_model.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/gauge_replication.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/gauge_atlas_audit.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/base_holdout.py --check
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/base_test_model.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_gauge128_base_opcount.py /private/tmp/mixed640-gaugebase-replay
(cd /private/tmp/mixed640-gaugebase-replay && MIXED640_HOLDOUT=/absolute/path/to/base-holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-gaugebase-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/selective_policy.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/selective_optimality_check.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/selective_holdout.py --check
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/selective_test_model.py
python3 experiments/prime-j0-mixed640-materialized-tree-20261013/native_selective64_opcount.py /private/tmp/mixed640-selective64-replay
(cd /private/tmp/mixed640-selective64-replay && MIXED640_HOLDOUT=/absolute/path/to/selective-holdout.json CARGO_TARGET_DIR=/private/tmp/mixed640-selective64-target cargo test --offline --locked --release --bin eisenstein_fixed source_frozen_holdout_matches_independent_binary -- --nocapture)
```
