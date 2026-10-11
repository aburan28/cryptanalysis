# Deferred affine-proof reconstruction

This experiment replaces the affine producer's full forward provenance with
pivot dependencies. It retains round35's fresh exact fixed-block symmetry,
packed ANF transport, complete root expansion, and the unchanged round34
independent checker. It changes how the producer constructs a certificate,
not the certificate wire format or the mathematical acceptance conditions.

## Construction and proof

For each residual Macaulay row, keep its original source ID: equation index
and multiplier slot in `(1, y_0, ..., y_(r-1))`. During highest-column-first
Gaussian reduction, toggle one dependency bit whenever an existing pivot row
is XORed into the current row. On insertion, store the reduced coefficient
row, its source ID, and its dependency bitset.

A pivot at column `p` can only have used pivots at columns greater than `p`.
Its exact relation is `R_p = source_p + sum(dependencies_p[q] * R_q)`, over
GF(2). If the current row becomes the constant one, start with that row's
source ID and dependency bitset. Repeatedly select the lowest remaining
dependency column, toggle its source into the affine multipliers, and XOR its
stored parents into the remaining bitset. Parents have strictly higher column
indices, so this expansion terminates and respects cancellation along multiple
paths. The result is exactly the equation-combination identity obtained by
carrying full provenance forward through those same row operations.

Rows are already polynomials in the Boolean quotient: multiplication uses
monomial-mask OR, including field relations. The independent checker reconstructs
and verifies the full identity from the original ANF. It does not consume or
trust the dependency graph. Every uncertified branch still receives exact
original-variable enumeration. Zero rows never become pivots. Pivot activity
is reset for each fresh residual system; stale dependencies are never read.

The coefficient and dependency bitsets each have at most three uint64 words
(176 cubic Boolean monomials for ten residual variables). Reconstructed
multipliers use the existing 32/64/128-bit equation representation and the
unchanged 64-bit wire limbs. All roots, including symmetry aliases, are expanded
before unchanged reduced-basis construction and independent certification.

## Budgets and accounting

The existing 67,108,864 query work bound and 65,536 branch work bound now charge
`rows + pivot-row XORs + reconstructed pivots` for this producer. Previous
producers charge `rows + pivot-row XORs`; the report records the distinction.
Reconstruction also has an explicit 67,108,864-pivot bound. A zero-bound test
forces failure to produce some affine identities and exercises exact fallback.
A budget failure returns no partial certificate as an answer.

`multiplier_stats.word_xors` counts forward coefficient-row uint64 XORs plus
the one dependency-bit toggle per pivot XOR. The separately reported
`dependency_toggles` is a subcount, so do not add it again. Reconstruction XORs
and source-bit toggles are separate counters. Reconstruction time is nested
inside affine generation and native evaluation, not an extra exclusive phase.
The independent original-ANF Python model checks all integer work counts,
capacity growth, symmetry expansion, and storage accounting.

The invariant dependency arrays and source IDs replace the full pivot-proof
array. Both their allocated bytes and total multiplier workspace are reported.
Existing specialization-table, proof, exact-enumeration, root and basis bounds
remain in effect. Accounted native allocations are not a process peak-RSS
measurement. Partial failure counters remain available even on an inconclusive
native result.

## Validation and measurements

The generic reconstruction rule is also exercised by the portable
[round35 pilot](../round35/research/deferred_proof_pilot.py). Native tests compare
complete wire proofs against the previous full-provenance producer, exercise
high dependency columns across word boundaries and equation bits through 128,
and cover CPU, requested Metal, UBSan, fresh workspace reuse, proof corruption,
and budget failures. Full frozen queries compare original equations, all roots,
bases, and curve witnesses through 27 variables. The offline auditor checks
full raw identities independently of the producer and its work model.

Use an ordinary Python interpreter; no Sage modules are imported. Build rounds
20, 23, 31, 32, 33, 34, 35, then 36 with their `build.py`. For macOS Metal, append
`--metal` to builds31 through36 and set `QUADRATIC_TEST_METAL=1` for tests.

```sh
python experiments/groebner-perf-20260924/round36/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round36 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round36/measure_deferred.py --correctness-only --repetitions 2 --output correctness.json.gz
python experiments/groebner-perf-20260924/round36/measure_deferred.py --correctness-only --large-controls --repetitions 2 --output wide-correctness.json.gz
python experiments/groebner-perf-20260924/round36/audit_deferred.py wide-correctness.json.gz
```

Append `--metal` to measurements for requested Metal arms. The shader remains
the existing full-branch constant-linearization kernel, limited to 31 features
and 32 equations. Deferred affine work runs on the CPU. Requested Metal at
24/27 variables is explicit CPU shape fallback. CPU stays the default.

The timing boundary includes public-point validation, fresh packed descent,
solving, full proof generation/copy/hash, independent certification, original
equation checks, curve replay, and reference-ANF evaluation. Target-independent
setup and extra offline reference audits are separate. No numerical pivots,
coefficients or target answers are reused between target queries.

Predeclared performance trials use 31 measured repetitions plus one warmup on
small controls and seven plus one warmup on the nine 21/24/27-variable controls,
with independent repeated trials. Arms are shuffled within each repetition.
Admission and every group-start/end/final one-minute load must be at most one
per logical CPU. Preserve failed, interrupted and ineligible attempts. GPU
promotion requires actual device execution and a complete-query win against
the fastest paired CPU. The wide comparison includes the previous symmetry
producer and the older expanded-enumeration exact baseline, so cumulative
ratios are measured directly rather than multiplied across experiments.

These are frozen planted PDP component controls. Candidate/IC/rho fields stay
null. This is a provenance-engineering experiment, not a novel F6 algorithm,
a general F4/F5 complexity improvement, or a full single-target IC result.
