# Affine-layer batch tree for fixed radix-14 scalar multiplication

The candidate changes the point-addition schedule for 128 independent secp256k1 scalar outputs. After the existing `371−τ` radix-14 recoder selects up to 15 affine points per scalar, it builds a balanced tree across each scalar's selected points. At each tree level it gathers every nonzero affine-addition denominator across all 128 scalars, performs one Montgomery-style batch inversion for the level, and finishes the affine additions. A full 15-leaf batch uses at most four shared field inversions, one per level; the reference forms XYZZ accumulators and batch-inverts only their final `ZZZ` values. The table and recoder stay the same.

The hash-guarded `native_affine_layer_overlay.py` applies to the source snapshot in the prior batch-size experiment. The release test `radix_136531_affine_layer_batch_matches_independent_binary` passed 128 independent frozen scalars against fixture points and a separate binary multiplier, plus zero, inverse-pair, and point-doubling cases. The source and binary hashes are in `tier1-affine-rules.json`; the Linux test and build logs are retained. A direct output-verified diagnostic returned 54.817360 ms for 12,288 outputs; it is exploratory and only selected the paired gate.

The frozen Tier 1 panel compares 128-output affine-layer batches with 128-output XYZZ final-inversion batches on the same 128 scalar fixture, 96 passes per arm, and 16 repeats of A/A, comparison, A/A. The serial runner alternates arm order and checks every output. The pair acceptance requires all 96 arms and 48 pairs valid, adjacent A/A ratios in `[0.90,1.11]`, and a paired bootstrap 95% interval wholly on one side of one. Table preparation and fixture loading precede the online interval; all point additions, inversions, and affine recovery are included.

The mathematical result is the composition of the prefix/reverse batch-inversion identity at every level with preservation of each tree's point sum when a pair is replaced by its affine group sum. The proof map is:

| Result | Lean declaration | Exact hypotheses and status |
| --- | --- | --- |
| One inverse gives a multiplicative inverse witness for each nonzero denominator | `BatchInverse.prefix_reverse_identity` in the parent experiment | Associative, commutative multiplication; exact prefix and reverse recurrences; inverse witness for the final product. Checked, all batch lengths. |
| A tree layer preserves the interpreted group sum | `AffineLayer.layer_preserves_sum` | Associative point addition and `decode(pair(a,b)) = decode(a)+decode(b)` for every pair, including identity and exceptional cases. Checked, all lists. |
| Any finite sequence of layers preserves that sum | `AffineLayer.layers_preserve_sum` | Same point-addition and pair hypotheses, arbitrary depth. Checked. |

`check_lean.sh` builds both theorem modules under Lean 4.34.1 and records `#print axioms` in `lean-check.log`: the layer theorems use `propext`, and the parent batch-inversion theorem uses `propext` and `Quot.sound`. There are no local axioms or placeholders. The concrete bridge from the Rust Montgomery-field operations and affine exceptional-case branches to `decode(pair(a,b)) = decode(a)+decode(b)` is checked by native holdout and boundary replay; a Lean model of that field/curve implementation remains open.

Batch-affine addition itself is established practice. [Eisentraeger, Lauter and Montgomery](https://arxiv.org/abs/math/0208038) study fast affine scalar arithmetic, and the [ZPrize MSM implementation notes](https://github.com/mitschabaude/montgomery/blob/main/doc/zprize22.md) describe batch-affine bucket reduction. This experiment applies per-layer inversion pooling across independent fixed-base `371−τ` scalar outputs with a frozen 15-leaf table schedule and paired CPU measurement.

## First paired panel: noise gate failed

The first serial job `c24e37df66ad4b1a891f1805798a0887` completed all 96 valid arms and 48 valid pairs with stable source and binary artifacts. Its descriptive median XYZZ/affine-layer ratio was 1.171280, with a repeat-bootstrap interval [1.157072, 1.177994]. The aggregate status is **unknown after the Tier 1 gate** because repeat 12 failed both adjacent A/A controls: 1.286019 before the comparison and 0.887931 after it, outside [0.90,1.11]. One affected A/A arm had 297 involuntary switches; the other slow A/A arm took 79.764 ms. The raw receipt is retained as `affine-layer-panel.tar.gz` (SHA-256 `71953a3e559ce82be0ba80abd77c6fd1922b8b4958cadc165c360f2859a5eaed`), unpacked under its job ID. `tier1-attempt1-analysis.json` and `tier1-attempt1-noise.json` preserve the audit and failure details.

A second independent serial job, `fe00f695389443f08d6cbf003f1a8b7e`, was submitted against the **unchanged** frozen manifest. Both jobs remain separate records; the second does not erase the first panel's failed gate.
