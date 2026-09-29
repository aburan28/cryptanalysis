# Conditional linear solving and exact Boolean certification

This opt-in experiment replaces full-cube evaluation for Boolean systems that
are affine in each of two declared variable blocks. The frozen two-summand
controls pass this condition; the three-summand controls do not. Existing CPU
and GPU dispatch remain unchanged. This is a specialized hybrid method, not a
new general F4/F5 algorithm or a novelty claim for “F6.”

The native ABI accepts packed coefficient words directly from native descent.
It does not construct Python polynomial sets, sort ANF masks, or repack equation
bits. Legacy uint32 masks and new uint64 masks are both accepted. A coefficient
bit denotes one GF(2) coordinate equation. The two separately compiled libraries
share only the ABI and bounds, not elimination or polynomial-proof code.

## Producer and independent completeness proof

Let x and y be the declared blocks. The accepted equations have the form
F(x,y) = A(x)y + b(x) over GF(2), with A and b affine in x.

The producer enumerates x in Gray-code order. Changing one bit updates the
coefficient columns by XOR. It eliminates columns of the equation-vector
matrix, obtains a particular solution and independent kernel directions for
every consistent branch, and emits the complete root set. The existing
Buchberger–Moeller frontier algorithm is adapted to 64-bit monomial masks to
interpolate a basis from that complete set.

The checker independently decodes the original packed ANF into equation rows.
It visits x in ordinary numeric order. Binary-increment prefix XORs update its
rows; this update and the producer's Gray-code update use different layouts and
orders. The checker computes rank and consistency with lowest-variable row
pivots, rather than the producer's highest-equation column pivots. Every
consistent branch contributes exactly 2^(number of y variables - rank) roots.
Branches partition all assignments, so their sum is the exact input-root count.

The proposed roots must be distinct and each must satisfy the original
equations, checked by direct term evaluation. Equality of their number with the
independent count establishes completeness. Missing branches, omitted roots,
duplicate roots and spurious roots cannot pass these conditions.

For the proposed basis, the checker requires:

1. Every basis polynomial vanishes on the complete input-root set.
2. The number of squarefree monomials outside the proposed leading ideal equals
   the independently established root count.
3. Leading monomials are minimal and all tails are standard.

In the Boolean coordinate algebra, every ideal is radical: the algebra is a
finite product of copies of GF(2). Including the Boolean field relations,
vanishing gives a lower bound on quotient dimension, while the completed
staircase gives the matching upper bound. This establishes ideal equality and
Gröbner completion; the minimality/tail checks establish the reduced Boolean
basis condition. The pure-Python audit separately specializes the original ANF,
uses descending row pivots, and traverses standard monomials with a deduplicated
set frontier. It does not execute archived source or trust native root counts.

This removes full-cube enumeration for the accepted family. The branch count is
still exponential in the x-block size. Output can also be exponential when a
branch has large nullity. The result is not a general polynomial-time Gröbner
algorithm or an asymptotic claim about the three-block IC workload.

## Bounds, ownership and fallback behavior

- x block: 1–20 bits; y block: at least one bit; total: at most 63 Boolean
  variables. There are 1–128 coordinate equations and at most 1,000,000 input
  terms. The equation count is distinct from the Boolean variable count.
- At most 256 complete roots may be emitted. Exceeding this cap returns
  inconclusive, never a partial basis.
- A complete sparse staircase is required, with a 256-element bound and
  1,000,000 divisibility-test budget. Exhaustion returns inconclusive.
- Nonzero raw terms nonlinear within either block are rejected as unsupported.
  Eligible duplicate terms cancel by XOR. Nonlinear terms that cancel only
  after aggregation are conservatively unsupported; zero coefficient terms are
  allowed after range validation.
- All coefficient layouts and numeric lengths are rebuilt on every call.
  Allocations and invariant dimensions may be reused; target answers are not
  cached. Input buffers must remain immutable during a call.
- Python and native locks protect each workspace and close. Different
  workspaces may execute independently. The result owns its data, and Python
  copies it before destroying the native result.
- This implementation has bounded work/storage but no hard per-call wall timer.
  The frozen CPU path remains available. No automatic routing change or hidden
  fallback is introduced; failed attempts remain inside measured query time.

The complete curve adapter retains the existing descent limit of 20 variables.
Larger certificate controls use generic packed bilinear systems, not a larger
curve-query implementation. This distinction is part of the evidence.

## Correctness and measurement

The suite checks all 256 two-variable/two-equation systems in optimized and
UBSan builds, randomized equations across both 64-bit limbs, rank-changing and
dependent equations, zero/unit ideals, exactly 256 roots and cap rejection,
nonlinear applicability failures, malformed ABI values, proof-budget rejection,
reuse, independent concurrent calls, and closed lifetimes.

Generic planted controls have 22, 24, 32, 48 and 63 Boolean variables. Both native
builds agree with independent Python branch counts and exact basis checks.
These establish correctness in the supported family; their wall diagnostics
are not admitted performance comparisons or full IC results.

Complete public-point tests retain direct original-equation checks and signed
curve replay. The paired benchmark has nine frozen controls: six 20-variable
two-summand systems, two smaller systems and one wide-field replay fallback.
Each call performs fresh descent, production, exact certification and replay.
Reusable setup and fixture generation are separate. An additional untouched
reference-ANF evaluation is charged; an extra Python curve audit is recorded
outside timing. One warmup is retained, followed by randomized paired repeats.

Initial, every group-start/end and final loads must pass the same declared
admission rule. Correctness-only reports cannot qualify. Every attempt remains
in a hash-chained journal, including failures, interruptions and rejected
admission windows. Source snapshots, native build receipts, binary identities,
full bases, root lists and signed witnesses are retained. The auditor requires
the same trusted source checkout and never imports archived code.

These are planted PDP component controls. Candidate IDs, IC online time and
rho online time remain null. No natural relation yield, full IC advantage,
subgroup-bit boundary or operation-count S ratio is established. A useful
component method must still be integrated into a complete one-unseen-target
IC pipeline and paired with rho using the same point and resource envelope.

## Reproduction

These are ordinary Python/C++ jobs, not Sage jobs:

~~~sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python experiments/groebner-perf-20260924/round27/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round27 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round27/branch_measure.py --repetitions 31 --output /tmp/conditional-paired.json.gz
python experiments/groebner-perf-20260924/round27/branch_audit.py /tmp/conditional-paired.json.gz
python experiments/groebner-perf-20260924/round27/large_certificates.py --output /tmp/conditional-large.json.gz
python experiments/groebner-perf-20260924/round27/large_certificates.py --audit /tmp/conditional-large.json.gz
~~~

Use a fresh output path; existing evidence cannot be overwritten. The workflow
rebuilds both libraries on Linux and macOS and retains explicit admission
failures. Native CPU correctness on those environments does not prove GPU
compatibility or a hardware speedup elsewhere.

## Prior art and remaining research

This is conditional linear algebra plus established interpolation. Bilinear
Gröbner algorithms are studied by
[Faugère, Safey El Din and Spaenlehauer](https://doi.org/10.1016/j.jsc.2010.10.014).
Specialized XL, mutant and hybrid methods appear in
[Baena, Cabarcas and Verbel](https://www.aimsciences.org/article/doi/10.3934/amc.2021047).
Their generic-system assumptions have not been proved for these descended
summation-polynomial inputs. Any F6 novelty claim needs a distinct method and
comparison with that literature.

General derivation/completion certificates, three-block structural methods,
overlapped independent GPU evaluation and the F4 matrix-reduction crossover
remain separate parts of the larger effort.

## Final-source physical M4 Pro measurement

The admitted 31-pair confirmation verifies all 576 complete queries, including
18 warmups. The six frozen 20-variable controls improve by 8.06–8.63× versus
the unchanged sparse CPU path. Two smaller controls also improve; the wide-field
case has a small 1.016× result in this run and was inconclusive in the initial
implementation run. It is not a robust large improvement. All individual
bootstrap intervals are unadjusted for multiple comparisons.

Host: physical Apple M4 Pro, 14 logical CPUs, macOS 26.6 ARM64, Python 3.13.1.
One-minute load was 11.102 at entry and 10.613 at exit; all group boundaries passed.
Load admission does not establish exclusive access to the host.

| Frozen control | Sparse CPU ms | Conditional ms | Paired gain [95% interval] |
| --- | ---: | ---: | --- |
| n31-m2-ell10-seed201 | 3.953 | 0.500 | 8.059 [7.797, 8.324] |
| n31-m2-ell10-seed202 | 3.948 | 0.488 | 8.133 [7.860, 8.427] |
| n31-m2-ell10-seed203 | 3.950 | 0.461 | 8.464 [8.163, 8.785] |
| n63-m2-ell10-seed201 | 4.722 | 0.546 | 8.627 [8.399, 8.852] |
| n63-m2-ell10-seed202 | 4.722 | 0.555 | 8.598 [8.305, 8.904] |
| n63-m2-ell10-seed203 | 4.745 | 0.566 | 8.497 [8.346, 8.654] |
| n31-m2-ell4-seed101 | 0.158 | 0.071 | 2.191 [2.073, 2.308] |
| n11-m2-ell3-seed101 | 0.137 | 0.051 | 2.684 [2.570, 2.799] |
| n83-m2-ell2-seed101 | 8.959 | 8.798 | 1.016 [1.007, 1.024] |

Times are medians; ratios are paired geometric means. The n31/n63 labels
identify field degrees, not subgroup-bit security. These are component
queries, with no recovered discrete logarithm or paired rho run.

The earlier checker independently reconstructed rows afresh for each branch.
Its admitted physical run verified 576 queries and measured 5.23–6.23× gains on
the six 20-variable controls. Its exact sources, journal and audit are retained
in the task archive referenced by results/prior-attempts.json. The final checker
uses independently decoded binary-increment row updates. The two implementations
were each paired with the frozen baseline; their cross-run timings are not a
paired estimate of the incremental checker improvement.

A first final-source timing attempt was not admitted at load 30.012 on 14 CPUs
and ran zero trials. Its admission receipt remains in results/. Final-source
correctness-only queries and all five larger exact certificates are also retained.
Every result includes source/binary identities; no archived native binary is
reused as cross-platform correctness evidence.
