# Exact N83 width-14 rectangle factor base

The affine width-14 base formed by four width-12 cosets at offsets
**(37,73), (37,82), (68,73), and (68,82)** has **8,532 distinct
signed-Frobenius columns** and **1,416,312 usable subgroup points**. It
is the unique maximum among all **2,914,905** rectangles made from four
distinct coordinates outside the frozen width-12 normal-basis span.
The [basis manifest](basis_manifest.json) specifies the affine offset,
14 basis vectors, orbit rule, and full sorted [key set](rectangle_keys.bin).

| Exact factor-base geometry | Prior shifted width 14 | Rectangle width 14 |
| --- | ---: | ---: |
| Affine `x` candidates | 16,384 | 16,384 |
| Signed-Frobenius columns `K` | 8,261 | **8,532** |
| Usable subgroup points `B=166K` | 1,371,326 | **1,416,312** |
| Full-base five-subset first moment `binom(B,5)/r` | 16,714.349889 | **19,641.774144** |

The rectangle adds **271 columns (3.28%)** at fixed affine dimension;
its exact five-subset first moment rises **17.51%**. That moment counts
combinatorial full-base subsets under a uniform group-sum model. It is
not a measured ordinary-query relation yield. A point-decomposition
circuit, useful rank, factor-base logs, target descent, and paired
single-target online comparison for this base remain future experiment
stages, so `candidate_id` is null.

## Exact finite screen and replay

Let `W=span_F2(gamma_1,...,gamma_12)` in the type-II normal basis of
`GF(2^83)`. Each edge `(i,j)` denotes the affine coset
`gamma_i+gamma_j+W` for `12 <= i < j <= 82`, where bit indices are zero
based. Four edges connecting a bipartition of four vertices form one
rectangle. Their union is an affine width-14 space: the chosen
rectangle has offset `gamma_37+gamma_73`, plus the two extra basis
vectors `gamma_73+gamma_82` and `gamma_37+gamma_68`. All three
vectors use only normal-basis coordinates, so each rotated leaf
coordinate remains an XOR of seed bits and a constant.

The [protocol](protocol.json) pins the prior exact 2,485-coset lift
[screen](../n83-geometric-two-shift12-20261012/screen.json), curve,
subgroup, normal-basis bridge, source hashes, and selection rule. The
[producer](rectangle.py) enumerates `3*binom(71,4)=2,914,905`
rectangles and scores each by its four exact rational lift counts.
The winner has **8,532** lifts; the next score is **8,509**. A folded
column requires at least one rational lift, so every other rectangle
has at most 8,509 columns. Exact cofactor-four projection and
sign/Frobenius folding of all 16,384 winner seeds gives **8,532**
columns, with no identity projection or repeated orbit key. The
strict gap certifies the unique optimum within this rectangle family.

The [independent Sage replay](independent_sage_replay.json) re-enumerates
all rectangles with a separate loop, constructs the four cosets in a
polynomial field, lifts points through the odd-degree half-trace
equation, checks the curve and subgroup, and independently reproduces
every sorted canonical key byte. The checked [Sage runtime
receipt](sage_runtime_info.json) was saved before execution. The
[read-only verifier](verify.py) checks hashes, counts, basis geometry,
both receipts, and the Lean axiom audit:

```sh
python3 experiments/n83-geometric-rectangle14-20261012/verify.py
```

The conditional counting implication and numerical comparisons have
checked declarations in [RectangleBound.lean](RectangleBound.lean),
built with the pinned [Lean toolchain](lean-toolchain). The
[axiom audit](lean-build.txt) reports no axioms. The full finite-field
census and the bridge from rational seeds to distinct projected orbit
keys are independently replayed computations; their formalization is
partial. The proof map is: `other_rectangle_below_winner` assumes the
8,509 lift bound and `columns <= validLifts`; the Sage replay checks
the finite census and complete winner orbit set; `winner_exceeds_prior_width14`
and `winner_usable_points` check the stated integer comparisons.

The next experiment should run the orbit-complete five-summand PDP
formula for this exact affine basis on the same frozen public point as
the prior width-14 stage. Measure ordinary-query status and verified
relation yield under the same 600-second cap, then account for useful
rank, final linear algebra, target descent, and matched rho before
interpreting an online speedup. Local construction time is recorded as
an exploratory shared-host diagnostic.
