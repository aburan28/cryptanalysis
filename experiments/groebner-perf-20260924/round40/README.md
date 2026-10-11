# Quadratic-first affine certificate constructor

This opt-in CPU experiment avoids some degree-one Macaulay matrices by
extracting affine constraints directly from the original quadratic residual
system. Existing solvers and automatic dispatch are unchanged. The independent
round34 checker validates the original-equation proof format without changes.

Eliminate quadratic columns while carrying original-row witnesses. The rows
with zero quadratic part form an affine subsystem. If its variable rank is
full, solve for the unique candidate assignment `a` and evaluate every
original equation there. A violated equation produces a contradiction identity
using the witnessed constraints `L_i = y_i + a_i` and the exact Boolean
identity `y_i*y_j + a_i*a_j = y_j*L_i + a_i*L_j`. Substituting the witnesses
gives affine multipliers of the original equations. The certificate retains
the existing constant-prefix plus sparse affine-record representation.

Rank deficiency, a satisfying assignment and budget exhaustion return to the
existing bounded Macaulay and exact enumeration paths. Projection work shares
the global and per-branch budgets with those paths, and failure statistics
include projection work. Fresh coefficients and pivots are required on every
query. This is a sufficient proof constructor, not a complete degree-one
decision procedure or a new asymptotic algorithm.

## Reproduce the correctness screen

Use ordinary Python with the existing native dependencies built. On a fresh
checkout, build rounds 20, 23, 31, 32, 33, 34, 35, 36 and 37 with their
`build.py` scripts. The CI workflow contains the exact sequence. Then run:

```sh
python3 experiments/groebner-perf-20260924/round40/build.py
python3 experiments/groebner-perf-20260924/round40/validate_native.py --output /absolute/path/to/new-correctness.json.gz
```

The screen covers 4,547 distinct systems in optimized and UBSan builds:
4,096 exhaustive two-variable, three-equation systems; the preceding 450
truth, word-boundary, duplicate-product, high-variable and symmetry controls;
and an explicit degree-one incompleteness counterexample. Four small-budget
controls preserve successful fallback and inconclusive outcomes. The frozen
18-input fixture supplies 54 complete queries across the earlier producer and
both candidate builds. New certificates can differ from old certificates, but
complete roots, canonical bases and signed curve witnesses must agree.
Candidate optimized and UBSan proofs and integer work must agree exactly.
The driver refuses to overwrite an existing output.

`ProjectionQuery` in `projection_query.py` exposes the complete CPU query.
The constructor explicitly rejects a requested Metal backend. GPU widening
and proof generation are separate experiments. Builds must be repeated on
each host; archived macOS binaries do not establish another platform's
compatibility. `projection_stats` reports the new work separately, including
bounded stack arrays; it is not a peak-memory measurement.

## Current evidence and limits

The archived physical M4 Pro prototype passed all 9,094 system runs, four
budget controls and 54 complete queries. A separate Python original-ANF audit
checked all 18 unique candidate query certificates, exhaustively enumerated
uncovered branches and matched the independently audited canonical bases and
curve witnesses. The source snapshot contained 199 baseline files. Repository
packaging is rebuilt and checked separately. The
[local package receipt](results/m4-pro-package-validation.json) confirms the
same 9,094 system runs, four budgets and 54 complete queries, with every proof
payload and synthetic integer count matching the independently audited
prototype. Portable CI records its own host, compiler, source and binary hashes.

Two paired prototype timing trials each completed 504 verified queries against
six earlier CPU implementations. Both failed the unchanged load gate: maxima
18.7017 and 14.7998 exceeded 14 logical CPUs. No qualified gain or dispatch
change follows. The retained analysis includes slight observed overhead at
21 variables and exploratory gains at 24/27 variables; the
[retained paired analysis](results/m4-pro-prototype-analysis.json) includes all
controls, paired ratios and intervals. These cannot support
a repeated speedup claim. At 27 variables, approximately 38,000 branches per
query used the new proof constructor, while rank and satisfying-assignment
fallbacks remained explicit. Fewer matrix operations alone do not prove
lower complete-query latency.

The bounded structural pilot also checked the common cubic-polarization
factor in all 1,008 sampled specializations of the original S4 ANFs, but this
generic implementation assumes no field normalization or special subspace.
Prior work such as [Polynomial XL](https://eprint.iacr.org/2021/1609) motivates
testing partial elimination; its quadratic-system hypotheses and heuristic
complexity bounds are not transferred to these degree-six original ANFs.
No global F4/F5 superiority, novel F6 asymptotics, ordinary relation yield or
complete IC/rho speedup is claimed.

Next: qualified paired complete-query timing, small-query regression controls,
and the strongest actually executed GPU comparisons. A separate normalization
hypothesis could reuse the invariant quadratic-column annihilator, but must
charge inversion, coefficient transformation and proof transport. Wider GPU
rows are needed before 24/27-variable residuals execute on the existing device
path. Both require their own correctness and performance gates.
