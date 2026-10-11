# Bounded sparse exact basis verification

This experiment removes work from the independent proof after Boolean truth
evaluation. The three complete-query arms are the unchanged round18 `cpu`,
`root-list` (compact independent roots with the frozen dense monomial check),
and `sparse` (compact roots and bounded standard-monomial enumeration).
The producer, packed input ABI, input validation, truth transform, direct
original-equation evaluator and curve replay are unchanged. No producer roots,
pivots or numerical workspaces enter the independent checker.

The source generator pins both the reference proof and round18 evaluator. It
generates an isolated library and an exact dense fallback. Existing CPU routing
is unchanged. This remains a 1–20-variable Boolean evaluation experiment, with
1–128 input equations; it does not remove truth enumeration or implement F4,
F5, or a novel F6 algorithm.

## Why the proof is unchanged

Work in `A = GF(2)[x_0,...,x_(n-1)] / (x_i^2+x_i)` with the frozen grevlex
order. The independent truth evaluator establishes the entire input zero set
`R`. For a proposed basis `B`, retain the original three checks:

1. Every polynomial in `B` vanishes at every point of `R`.
2. The number `D` of squarefree monomials not divisible by any leading monomial
   of `B` equals `|R|`.
3. Leading monomials are minimal and every tail monomial is standard.

Including the Boolean field relations, the standard-monomial count bounds the
dimension of the quotient by `B` from above. Vanishing on `R` gives the reverse
bound `dim(A/<B>) >= |R|`. Equality of the two bounds proves ideal equality and
that the declared leading monomials generate the leading ideal. The final
minimality and tail checks retain the original reduced-basis condition.
Boolean ideals are radical because the Boolean coordinate algebra is a finite
product of copies of GF(2). These are the same proof obligations as the pinned
reference, with different representations for two finite sets.

The allowed squarefree monomials are downward closed under divisibility. Start
at mask zero and add only variable indices greater than the current highest
index. Every subset has exactly one parent in this traversal. Every allowed
mask is reached because its prefixes are allowed, and no mask is duplicated.
An excluded prefix can be pruned because all its multiples are excluded.
Consequently, a completed traversal counts the same set as the dense reference.
The empty set (leading monomial 1) and the 256-element boundary are explicit
tests. The exact count is independent of basis-row order.

Two fixed arrays of 256 masks hold compact roots and standard monomials. A
65,536-test membership budget bounds speculative divisibility work. A larger
root set bypasses this path; a 257th standard monomial or an exhausted budget
runs the exact dense check. A truncated traversal is never reported as an exact
dimension, including for invalid certificates. Previously spent work stays
inside the proof timer. The original rejection codes and certificate fields
are preserved. A separate test-only library lowers the budget to eight to force
the fallback on valid and invalid inputs.

Allocations may be retained between queries, but all root lists, leading terms,
logical lengths and counters are rebuilt from the current coefficients/basis.
The unchanged Python lock protects certification, equation evaluation and close.
Returned proof counters describe sparse work and fallback decisions, not a
complete operation count for the solver. `scratch_bytes` covers evaluation and
retained proof workspace, while `dense_table_bytes` reports the temporary dense
monomial bitset separately; neither is a full-process peak-memory measurement.

## Validation and measurement

The test suite reuses the frozen checker's malformed ABI, wide equation-limb,
duplicate-parity, closed-lifetime, concurrent-call and zero/many-root tests.
It additionally compares all 256 three-variable Boolean polynomials and
corrupted output bases against the unchanged checker, in all proof modes and
optimized/UBSan builds: 10,734 exact certificate comparisons. There are also
240 randomized parity comparisons, 7,328 direct equation evaluations and 72
complete-query comparisons over three field sizes, two builds and fresh full
public targets, with Python ANF materialization forbidden.

Dedicated cases cover nonzero roots through 20 variables, exactly 256 roots,
both mathematical storage boundaries, forced work-budget fallback, bad leading
terms/tails, and reuse after success and failure. Audit tests corrupt source and
binary identities, proof counters, witness coordinates, phase totals and
coverage. Journal tests retain interruption, truncation and sync-failure rules.

The complete-query benchmark retains the same 16 planted controls as round22,
including 18- and 20-variable shapes and a wide-field replay fallback. Setup is
separate; every query performs fresh descent, solving, complete certification,
original-equation checks, full signed curve replay and reference-ANF evaluation.
One warmup and randomized paired repetitions are retained. Initial, every
paired-group start/end, and final one-minute loads must pass the fixed admission
rule. Correctness-only traces are permanently ineligible for speed claims.
All failures remain rows. Load admission does not prove an exclusive host.

These are PDP component controls, with IC candidate IDs and IC/rho online times
null. They are not natural relation-yield estimates or full discrete-log
recoveries. A component winner must still be integrated and measured through
one independently verified IC target, with rho on the same public point.

## Reproduce

From the repository root, using ordinary Python (these are not Sage jobs):

```sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round23 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round23/benchmark.py --repetitions 31 --output /tmp/sparse-proof.json.gz
python experiments/groebner-perf-20260924/round23/audit.py /tmp/sparse-proof.json.gz
python experiments/groebner-perf-20260924/round23/verify_evidence.py
```

The workflow rebuilds and checks the native code on Linux and macOS, then
attempts a bounded 31-pair measurement on each runner. Journals, aggregate
reports, build receipts, all snapshotted sources and raw failures are retained.
The receipt auditor verifies source/generation identities and complete-query
semantics; the byte inventory binds the committed evidence. It does not reuse
one platform's native binaries to claim correctness on another.


## Physical M4 Pro measurements

Both local 31-pair runs pass the fixed load rule and verify all 1,536 complete
queries each, including 48 warmups. The initial run qualified all six
18-variable controls at 1.017–1.031× complete-query gains. After removing three
trailing blank lines, the final-source confirmation qualifies five of those
six at 1.016–1.028×; seed102 is inconclusive. Smaller controls and most
20-variable controls are also inconclusive. No broad or uniform speedup is
claimed, and no automatic routing changes. These are modest component gains,
not another 2×.

The exact initial source, receipts and full results are preserved in the task
archive identified by `results/prior-attempts.json`. The committed reports below
bind to the final source, with all negative and inconclusive cells retained.
The 22 test groups pass against the rebuilt final native library.

The sparse proof eliminates the dense monomial bitset on every verified
benchmark query. The initial run measured about 0.0033–0.0037 ms at 18 variables
and 0.0060–0.0065 ms at 20 variables, versus approximately 0.029 and 0.12 ms for
the root-list arm's dense proof. These internal diagnostics cannot be added as
marginal medians to form total costs. Truth evaluation remains the principal
CPU-verifier cost. The correctness suite exercises every fallback explicitly.

| Final-source control | CPU median ms | Root-list median ms | Sparse median ms | Paired CPU/sparse [95% interval] |
| --- | ---: | ---: | ---: | --- |
| n31-m3-ell6-seed101 | 2.088 | 2.058 | 2.042 | 1.027 [1.016, 1.039] |
| n31-m3-ell6-seed102 | 2.144 | 2.153 | 2.137 | 0.992 [0.894, 1.084] |
| n31-m3-ell6-seed103 | 2.127 | 2.110 | 2.090 | 1.021 [1.009, 1.035] |
| n31-m3-ell6-seed104 | 2.084 | 2.070 | 2.055 | 1.016 [1.004, 1.028] |
| n31-m3-ell6-seed105 | 2.089 | 2.088 | 2.054 | 1.023 [1.014, 1.033] |
| n31-m3-ell6-seed106 | 2.106 | 2.090 | 2.065 | 1.028 [1.019, 1.036] |
| n31-m3-ell3-seed101 | 0.214 | 0.209 | 0.203 | 1.039 [0.996, 1.087] |
| n31-m3-ell4-seed101 | 0.281 | 0.277 | 0.284 | 1.003 [0.958, 1.048] |
| n11-m3-ell2-seed101 | 0.143 | 0.150 | 0.153 | 0.981 [0.918, 1.048] |
| n83-m3-ell2-seed101 | 15.378 | 15.301 | 15.385 | 0.997 [0.977, 1.021] |
| n31-m2-ell10-seed201 | 5.817 | 5.400 | 5.922 | 0.982 [0.912, 1.047] |
| n31-m2-ell10-seed202 | 4.174 | 4.117 | 3.968 | 1.051 [1.040, 1.062] |
| n31-m2-ell10-seed203 | 4.255 | 4.192 | 4.045 | 1.027 [0.997, 1.053] |
| n63-m2-ell10-seed201 | 5.000 | 4.963 | 4.877 | 1.009 [0.947, 1.060] |
| n63-m2-ell10-seed202 | 5.920 | 6.526 | 5.057 | 1.011 [0.952, 1.070] |
| n63-m2-ell10-seed203 | 4.924 | 4.887 | 4.770 | 1.031 [1.020, 1.042] |

The reports contain full host/build/source identities. Initial admission
sidecars retain pre-work counters; final attempt counts and qualification are
in journal-matched aggregates. The per-control bootstrap intervals do not
constitute a multiple-comparison-adjusted selection procedure. Cross-platform
confirmation must be read from actual PR workflow artifacts before claiming it.
