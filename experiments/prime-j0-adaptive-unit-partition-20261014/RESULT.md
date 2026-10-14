# Adaptive unit-class partition for compact norm-4,831 multiplication

The exact 20-digit source-operation screen and a native evaluator identify a
smaller schedule family for the 64-byte affine digit table: evaluate one or
two unit groups, choosing each group's orientation from the recoded scalar.
Under the declared XYZZ and Solinas product model, a three-group schedule is
always dominated when all three unit classes occur. The two-group option is
selected for 57 of the 231 class-count triples with 20 nonzero digits; the
one-group option is selected for 174. The native selector passed five
correctness test families. No controlled wall-time comparison has been run.

For each unit power `c` in `{0,1,2}`, let `S_c` be the sum of selected signed
affine points before applying the cube-root endomorphism `ω`. The target sum
is `S_0 + ω(S_1) + ω²(S_2)`. A group containing classes `C` and stored in
orientation `j` accumulates `Σ_{c∈C} ω^(c-j) S_c` and is rotated by `ω^j`
once before the groups are joined. For example, merging classes one and two
uses `S_0 + ω(S_1 + ω(S_2))`. Additivity of `ω` makes this exactly the target
sum. The Python audit checks all 57 canonical partition/orientation schedules
on both coefficient-basis vectors for each class. The Lean module proves
additivity, the order-three action, the class-one/two merge, and the
three-group cost dominance theorem.

The model charges 36 source-level integer products per generic Montgomery
field multiplication and 23 per Solinas cube-root multiplication, as counted
in the existing field implementations. A nontrivial XYZZ mixed addition has
eight generic field multiplications; a projective XYZZ join has twelve.
Squares, field additions, recoding, table reads, branching, and instruction
scheduling are outside this product-only model. With `n` nonzero digits and
one nonzero terminal, three occupied groups cost `(n−2)·288 + 2·432 + 2·23`.
Merging a class of size `m` into another group costs at most
`(n−1)·288 + 432 + (m+2)·23`. Since `n≤20`, at least one of three occupied
classes has `m≤6`, so the merge saves at least `144−6·23=6` source products.
The theorem preserves the exact `n≤20` and three-nonempty-class hypotheses;
the terminal and orientation costs are explicit in the model.

`adaptive_schedule.py` exhausts all 231 triples summing to 20 and chooses a
minimum-cost partition with deterministic tie breaks. Its frozen
`schedule-audit.json` reports 167 triples beating a fixed orientation-zero
one-group path. Under an **assumed independent uniform distribution** of
the three unit powers, the expected modeled saving against that path is
41.897 source products per scalar and the two-group choice probability is
0.2359. This distribution is an analytic reference, not a measured scalar
law. The largest saving among count triples is 437 products. These small
modeled savings may be erased by the extra recoding pass or branch dispatch;
the screen gives a concrete hypothesis for an isolated native comparison.

`adaptive_overlay.py` generates a 1,771-byte schedule table for all count
triples with up to 20 nonzero digits and verifies its index formula at every
entry. It replaces the three-bucket evaluator's digit path with a recode
pass followed by one or two oriented accumulators. The plan table raises
retained memory from 1,425,154 to **1,426,925 bytes**, still below the
1,940,994-byte direct two-X table. A second clean generation produced
byte-identical Rust source. `overlay-receipt.json` pins both generated source
hashes and the plan digest.

The release native suite passed all 4,831 residue codes, 43,479 quotient
cases, 96,720 unit images, 5,680 terminal indices, 128 frozen scalars, and
518 additional deterministic or boundary scalars against independent binary
point multiplication. On frozen fixture case 0, the evaluator reports 20
nontrivial mixed additions, no projective joins, 12 digit cube-root
products, one final bucket rotation, 20 digit reads, one terminal read, and
12 sign flips. The output point matches the fixture. The local wall-time
field in that log is a contended-host diagnostic and is not used as a speedup.
`native-validation.json` records the arm64 macOS compiler, source and binary
hashes, fixture digest, and exact counts; `native-test.log`,
`native-build.log`, and `native-case0.log` retain the raw local outputs.

Proof map:

| Result | Lean declaration | Hypotheses | Verification |
| --- | --- | --- | --- |
| Cube-root additivity | `omega_add` | arbitrary coefficient pairs | built, standard `propext` and `Quot.sound` |
| Order-three action | `omega_cube` | arbitrary coefficient pair | built, standard `propext` and `Quot.sound` |
| Merge classes one and two | `merge_unit_classes_1_2` | arbitrary three aggregate pairs | built, standard `propext` and `Quot.sound` |
| Three-group cost dominance | `three_way_cost_dominated` | three positive class counts summing to at most 20; declared product costs | built, standard `propext` and `Quot.sound` |

The proof uses Lean 4.34.1. The checked dependency source
`SplitPrimeRadix.lean` has SHA-256
`090cc56ea8ded7761c14af1e9670e7597deef6d030fa43ed52abed44ba6d05df`;
this theorem source has SHA-256
`595d5df02863a91ef4d67ce3f2e8bb6311a9af1c7b8e3c8279715b8c8380ece6`.
`dependency-lean-check.log` and `lean-check.log` record the rebuilt modules
and `#print axioms` results. The scheduler's correspondence to the compiled
selector is checked by the 1,771-entry generator index audit, byte-identical
generation, and native scalar replay. A full Lean theorem for every one of
the 57 orientation/partition encodings remains open; the central merge and
cost-dominance results above are kernel checked.

Reproduce the model and proof from this checkout:

```sh
python3 experiments/prime-j0-adaptive-unit-partition-20261014/adaptive_schedule.py
mkdir -p /private/tmp/adaptive-unit-lean
/Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean -o /private/tmp/adaptive-unit-lean/SplitPrimeRadix.olean experiments/prime-j0-mixed640-materialized-tree-20261013/SplitPrimeRadix.lean
LEAN_PATH=/private/tmp/adaptive-unit-lean /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean experiments/prime-j0-adaptive-unit-partition-20261014/AdaptiveUnitPartition.lean
```

Generate and test the native evaluator after preparing the same source crate
used by the three-bucket overlay:

```sh
python3 experiments/prime-j0-three-bucket-20261014/three_bucket_overlay.py /private/tmp/adaptive-native-replay
python3 experiments/prime-j0-adaptive-unit-partition-20261014/adaptive_overlay.py /private/tmp/adaptive-native-replay
CARGO_TARGET_DIR=/private/tmp/adaptive-native-replay-target cargo test --manifest-path /private/tmp/adaptive-native-replay/Cargo.toml --offline --locked --release --bin eisenstein_fixed split_prime_ -- --test-threads=1 --nocapture
```

The next gate is a fresh calibrated Tier 1 or Tier 0 panel comparing the
native selector with the direct two-X and three-bucket kernels on identical
scalars and resources. The initial RunPod calibration panel was invalidated
by two noise failures, so its point ratios cannot be reused as this
candidate's timing evidence.
