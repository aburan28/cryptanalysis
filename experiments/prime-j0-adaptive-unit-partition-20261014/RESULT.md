# Adaptive unit-class partition for compact norm-4,831 multiplication

The exact 20-digit source-operation screen identifies a smaller schedule
family for the 64-byte affine digit table: evaluate one or two unit groups,
choosing each group's orientation from the recoded scalar. Under the declared
XYZZ and Solinas product model, a three-group schedule is always dominated
when all three unit classes occur. The two-group option is selected for 57 of
the 231 class-count triples with 20 nonzero digits; the one-group option is
selected for 174. This is a cost-model result. No wall-time advantage is
assigned to it.

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
the screen gives a concrete falsifier before a costly native build.

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
and `#print axioms` results. The general Python scheduler's correspondence
to a compiled point evaluator remains an implementation bridge, checked here
by the coefficient-basis audit and reserved for native scalar replay before
any performance claim.

Reproduce the model and proof from this checkout:

```sh
python3 experiments/prime-j0-adaptive-unit-partition-20261014/adaptive_schedule.py
mkdir -p /private/tmp/adaptive-unit-lean
/Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean -o /private/tmp/adaptive-unit-lean/SplitPrimeRadix.olean experiments/prime-j0-mixed640-materialized-tree-20261013/SplitPrimeRadix.lean
LEAN_PATH=/private/tmp/adaptive-unit-lean /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean experiments/prime-j0-adaptive-unit-partition-20261014/AdaptiveUnitPartition.lean
```

The next implementation gate is a native one-group/two-group selector on the
same 64-byte table, with independent scalar replay. Only after correctness
passes should its full-operation time be compared with the direct two-X and
three-bucket kernels in a fresh calibrated Tier 1 or Tier 0 panel.
