# Q1442: conditional selected-W7 factor-base screen

This is a **design calculation**, not a measured point-decomposition cost or
an ECC2K-130 solve. It asks whether using only some of the W7 normal-basis
orbits could balance ordinary-query coverage and final matrix width better
than either the exact W≤6 base or the sampled full W≤7 proposal. The curve
is `EC1N131Ckb1h6816f880945e`; N131 names the field degree, not the
subgroup bit length. Q1442 has `candidate_id: null` and `isogeny: "none"`.

The input geometry is the [exact Q1414 W≤6 base](../runs/n131_q1414_exact_uniform_query_bound.json),
with B=6,559,634,788 and K=25,036,774, and the [Q1437 full W≤7 sample](../q1437_weight7_frontier/README.md),
whose conditional center has B≈118.636 billion and K≈452.809 million. Q1442
does **not** construct its proposed selected base: actual selected B, K, and
set digest remain null. Selection would need a deterministic signed-Frobenius
orbit rule and exact subgroup/projection collision checks before an `IC1`
candidate could be considered.

## Declared model

Let `B` be the usable point count before sign/Frobenius folding. The model
assumes 262 points per folded column (two signs and 131 Frobenius shifts),
no projection collisions, and independent uniform sums of distinct
four-point subsets in the exact nonidentity subgroup. It assigns

`lambda(B) = C(B,4)/(r-1)`, `p(B) = 1-exp(-lambda(B))`, `K(B)=B/262`.

It then optimistically assumes each covered ordinary query supplies **one
verified novel row**, and sizes the ideal mean query count as `K/p`. If every
query traverses all B points once, scan actions are `B*K/p`. The action is
an abstract count of tested points, not a field operation or CPU cycle.
Setup, base construction, query generation, matrix work, target descent,
replay, and any gap between natural coverage and a solver's actual recovery
rate are set to zero in that scan total. The optional `4K²` matrix number is
a logical row-action proxy in a different uncalibrated unit; it is not added
to scan actions or presented as a measured matrix solve.

Under the continuous approximation `lambda≈B⁴/(24(r-1))`, the scan objective
has its minimum where `exp(lambda)-1=2*lambda`, at `lambda≈1.25643`. The
screen rounds the resulting B to a multiple of 262 and evaluates the exact
binomial expression. The [independent audit](verification.json) checks the
frozen input/source hashes, recomputes scan totals, and checks that the
adjacent orbit counts are more expensive within this model.

| Geometry | B used in model | K used in model | Poisson coverage model | Ideal queries for K novel rows | One-action full scan | Allowed actions per tested point under `2^61`, all else zero |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Exact W≤6 geometry | 6.560 billion | 25.037 million | 0.1072 | 233.63 million | `2^60.411` | 1.505 |
| **Selected W7 conditional model** | **11.969 billion** | **45.683 million** | **0.7153** | **63.86 million** | **`2^59.407`** | **3.017** |
| Full W≤7 sample center | 118.636 billion | 452.809 million | effectively 1 | 452.81 million | `2^65.542` | 0.0429 |

These are three **model rows**, not three measured candidates. The exact
Q1414 uniform-query 95%-rank necessary bound and Q1441 full-scan gate are
separate, rigorous statements under their declared policies. Q1442's
Poisson hit rates, perfect one-row novelty, and selected-W7 collision-free
capacity have not been established. The 3.017-action allowance is therefore
neither a field-operation budget nor evidence that an actual full scan fits.

## Decision and next experiment

The selected-W7 range is worth retaining as a possible N131 factor-base
design; the sampled full W7 base is too wide for a one-row-per-query full
scan under Q1441's abstract budget. The **next solver gate** remains an exact
target-conditioned sparse-pair witness method on the exact N53/N83 bases.
It must first recover known pair witnesses without leaf pins, then produce
ordinary four-point relations with all failed attempts charged. A verified
ordinary N83 relation and novel-rank panel are needed before replacing this
coverage model with measured useful-row rates. Constructing a selected N131
base or launching a challenge before that would not close the missing solver
cost. The complete N131 `2^x` and challenge gate remain null/false in the
[result](result.json) and [work ledger](../work_ledger.json).

The [protocol](protocol.json) was committed before emitting the result. The
calculation uses Python's standard library only; it is not a Sage job. It
can be reproduced without overwriting archived outputs:

```sh
python3 experiments/compact-s3-m4-20261003/q1442_selected_base_screen/screen.py --check
python3 experiments/compact-s3-m4-20261003/q1442_selected_base_screen/verify.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```
