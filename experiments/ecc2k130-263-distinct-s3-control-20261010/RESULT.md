# Finite six-distinct controls remove the fast first-leaf x recall

The exact fixed six-leaf witness returned independently verified SAT on both
the ECC2K-130 source and its oriented degree-263 descendant, while a
one-bit-changed target returned explicit UNSAT on both. With exactly one
131-bit leaf coordinate released, all four x0/z0/x5/z5 cells on each curve
entered active CryptoMiniSat search and ended `BOUNDED_UNKNOWN` under the
frozen limits. In particular, x0 changed from the prior exceptional
witness's fast SAT recall to a bounded search on **both** curves. The new
witness has six distinct selected leaves and four finite S3 intermediates;
its six fourfold projections are distinct, nonidentity points in the
prime-order subgroup. This supports treating the earlier x0 result as a
cancellation-branch shortcut, while leaving ordinary-query relation yield
to the next gate. The [archive-only audit](runs/R1/audit.json) independently
reconstructed all twelve exact inputs and verified the solver transcripts.

The [precommitted protocol](PROTOCOL.md) selects archived native-W24 geometry
rows 0–5 on each curve, in mask order, from the checked
[native geometry](../ecc2k130-263-native-w24-m6-20261010/runs/R1/geometry_controls.json).
The all-plus raw sum supplies each control target; the two targets and every
point are in the [Sage-checked witness](runs/R1/witness.json). This is a new
synthetic control-target law, separate from the held-out Q1420 public point.
Curve IDs are `EC1N131Ckb1h136f03e58c98` and
`EC1N131Cbinh833014327b07`; each exact W24 base has `B=16,772,828`
subgroup-usable points. Raw leaves may carry cofactor torsion; the witness
checks their `[4]P` subgroup projections and the signed raw sum separately.
Protocol/source commit `cf2a53071` and checked-witness/input commit
`9bbe5ff27` preceded the first solver run.

Each curve has one losslessly archived base XCNF with the target-mux choices
`(target_x, target_x xor 1, target_x xor 1, target_x xor 1)`. The source
base has 340,590 variables, 334,948 ordinary clauses, and 227,701 native
XORs; the descendant base has 345,041 variables, 334,390 clauses, and
232,290 XORs. Base construction took 4.732 and 5.148 seconds respectively,
with process RSS peaks of 298,434,560 and 299,597,824 bytes. The
[source](runs/R1/source_cells.json) and
[descendant](runs/R1/descendant_native_cells.json) receipts identify their
raw/gzip base hashes, named-input maps, twelve fixed-unit deltas, complete
input hashes, and formula byte counts. Both fixed controls use 2,246 unit
clauses; each single-coordinate release uses 2,115.

| Curve | Cell | Audited status | Solver wall s | Peak sampled RSS MiB | Final conflicts | Restart rows | Guard |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Source | fixed positive | `SAT_VERIFIED_GROUP` | 0.531 | 128.547 | 0 | 1 | none |
| Source | changed target | `UNSAT` | 0.265 | 3.719 | 0 | 0 | none |
| Source | x0 free | `BOUNDED_UNKNOWN` | 122.141 | 234.828 | 981,980 | 1,576 | none |
| Source | z0 free | `BOUNDED_UNKNOWN` | 150.197 | 191.219 | unprinted | 1,637 | wall |
| Source | x5 free | `BOUNDED_UNKNOWN` | 149.202 | 254.109 | 793,698 | 1,331 | none |
| Source | z5 free | `BOUNDED_UNKNOWN` | 150.119 | 166.812 | unprinted | 1,440 | wall |
| Descendant native | fixed positive | `SAT_VERIFIED_GROUP` | 0.515 | 130.516 | 0 | 1 | none |
| Descendant native | changed target | `UNSAT` | 0.515 | 5.234 | 0 | 0 | none |
| Descendant native | x0 free | `BOUNDED_UNKNOWN` | 122.039 | 229.484 | 1,104,862 | 1,761 | none |
| Descendant native | z0 free | `BOUNDED_UNKNOWN` | 121.804 | 214.156 | 926,430 | 1,455 | none |
| Descendant native | x5 free | `BOUNDED_UNKNOWN` | 122.335 | 233.438 | 748,212 | 1,310 | none |
| Descendant native | z5 free | `BOUNDED_UNKNOWN` | 124.591 | 169.016 | 737,630 | 1,288 | none |

The positive source assignment passed 337,194 ordinary clauses and 227,701
native XORs; the descendant assignment passed 336,636 clauses and 232,290
XORs. Each decoded model has the six archived distinct masks, finite pair
and tree states, and exactly one matching sign assignment: all plus. Its
signed sum is the exact Sage-checked target point. The negative target
differs only in x bit zero while every witness input stays fixed. The six
bounded cells that exited through the solver printed `s INDETERMINATE` and
their final conflict counts. The source z0/z5 cells reached the 150-second
external wall guard; their final conflict counts were not printed, and the
audit retains their 1,637/1,440 restart-progress rows. No 4-GiB RSS guard
fired. All twelve solver stdout archives, stderr files, receipts, and input
deltas are committed. An independent second audit produced byte-identical
JSON.

The [environment receipt](runs/R1/environment.json) records macOS 26.6,
Apple M4 Pro, checked Sage 10.10.rc0 runtime, Python 3.13.1, CryptoMiniSat
5.14.7 binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
one solver thread, and the exact solver wall interval. Host-wide CPU
isolation was not established; the wall values are exploratory stage costs.
This panel changes the selected six leaves and control target between the
exceptional and finite fixtures, so it tests the solver behavior across
those structures but does not isolate a single causal equation.

The next concrete encoding gate is an **exact selector-weighted bilinear
leaf product** against these frozen inputs. Since W24 gives
`w = sum_j s_j b_j` and `u = sum_j s_j h_j`, field bilinearity gives
`w*z = sum_j s_j*(b_j*z)` and
`u*(x+alpha) = sum_j s_j*(h_j*(x+alpha))`.
The `b_j` are sparse trace-adjusted monomials, making the `w*z` side a
particularly focused first implementation. Build source/descendant
`w*z`-only and both-product variants, prove Boolean equivalence on sampled
and boundary masks, compare XCNF dimensions and positive/negative controls,
then run the same coordinate cells with the exact resource cap. Only a
verified ordinary relation advances to the frozen equal-B yield/rank
comparison. This control remains proposal `Q1420` with `candidate_id: null`
while natural relation yield, novel rank, final matrix, target descent, and
one-target online costs are unset.

Reproduce the audit using the committed archives:

```sh
python3 -B experiments/ecc2k130-263-distinct-s3-control-20261010/audit.py \
  --scratch-dir /private/tmp --out /private/tmp/distinct-s3-audit-replay.json
cmp /private/tmp/distinct-s3-audit-replay.json \
  experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/audit.json
```
