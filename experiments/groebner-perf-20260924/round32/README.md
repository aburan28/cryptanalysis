# Independently checked quadratic branch certificates

Round31's conditional quadratic solver made complete 18-variable public-point
queries faster, but still used an independent exhaustive checker with a
20-variable input limit. This experiment supplies an algebraic contradiction
certificate for each pruned branch. A separate library reconstructs the
specialized equations and checks every identity. It exhaustively checks the
original residual variables in every branch without a certificate.

This is an opt-in structured Boolean solver/checker experiment. Existing F4,
F5, round31, and CPU dispatch remain unchanged. It does not establish a new
general Gröbner-basis algorithm, an asymptotic improvement, or a full IC win.
The public-point fixtures are planted correctness controls, not measurements
of natural relation yield. They recover a decomposition, not a discrete log;
IC candidate IDs and IC/rho online times remain null.

## Exact certificate and independent checking

Partition Boolean variables into `x` fixed variables and `y` residual variables.
The input is packed original ANF, with up to 128 equations. Residual degree must
be at most two. For each of the `2^x` fixed assignments, the producer emits an
equation-combination vector `u` (one or two uint64 limbs):

* If `u != 0`, it claims the polynomial identity `sum_i u_i F_i(y) = 1`.
  The checker reconstructs every original residual coefficient and verifies
  constant parity one and every nonconstant parity zero. Such a branch has
  no root. This is stronger than merely trusting an inconsistent linearization.
* If `u == 0`, the checker enumerates **all `2^y` original assignments** in
  that branch. Missing certificates can increase work, but cannot remove roots.

The CPU producer derives `u` as a dual functional of its column echelon basis.
The Metal producer tracks equation combinations through its exact row swaps
and XOR operations. Neither implementation supplies coefficient tables or
pivots to the checker. The checker uses a separately decoded feature-major
layout, numeric residual-monomial order, and descending subset-transform bits;
the producer uses a branch-major layout, singles/pairs order, and ascending bits.
The checker does not call the producer or basis interpolation code.

All supplied roots must be sorted, distinct, within the ring, and directly
satisfy the original ANF. Their number must equal the checker's exact total.
This proves completeness. Next the checker verifies that the proposed basis
vanishes on those roots, has minimal leading monomials and standard tails,
and has exactly that many squarefree standard monomials.

The latter proves ideal equality and the reduced Boolean Gröbner basis claim:
in `F2[z]/(z_i^2+z_i)`, every ideal is the vanishing ideal of its Boolean zero
set. The proposed basis ideal lies in the input's vanishing ideal. Its leading
monomials provide a quotient-dimension upper bound equal to the known number
of roots, while evaluation on those roots provides the matching lower bound.
Equality proves both ideal equality and completeness of the leading ideal.
Minimal leads and standard tails then give reducedness in the declared order.
Boolean field relations are part of this argument, not omitted equations.

The independent Python audit is an additional, outside-timing check. It
reconstructs the untouched reference ANF, exhaustively evaluates the full
Boolean space using small truth-table chunks, checks every retained
contradiction by direct term specialization, recomputes branch rank/fallback
statistics, checks the basis, and replays the complete curve witness. It never
executes archived source text or native solver code.

## Scope and limits

| Component | Bound and failure behavior |
| --- | --- |
| Partition | `1 <= x <= 20`, `1 <= y <= 10`, `x+y <= 30`; actual feasible dimensions also obey memory limits |
| Equations | 1–128 packed Boolean equations |
| Specialization tables | At most 64 MiB per producer/checker table; the producer currently uses 128-bit words even for narrow equations |
| Complete roots | At most 256; exceeding this is inconclusive |
| Producer enumeration | At most 4,194,304 lifted or fallback assignments |
| Checker enumeration | At most 4,194,304 original residual assignments |
| Basis proof | At most 1,000,000 staircase divisibility checks |
| Metal | 32-wide SIMD groups, at least 128 threads/group, equations <=32, residual features <=31; unsupported shapes explicitly use CPU |
| Complete point adapter | Three coordinate blocks, up to 30 variables subject to the table limits; native odd-degree field replay <=63, explicit Python replay fallback above that |
| Offline exhaustive oracle | At most 24 variables, 16,384-bit truth chunks |

Budget exhaustion never returns a partial basis as certified. A requested
Metal backend whose device/capabilities are absent fails explicitly. Shape
fallbacks remain visible. The 24-variable public-point control has 36 residual
features and uses the CPU fallback even when Metal is requested.

Retained layouts, support maps, native allocations, pipelines and device
buffers depend only on the ring/shape. Coefficients, specialization tables,
solving, certificates and checks are fresh for every query. Proof storage is
fresh per produced result. Packed ANF buffers are passed directly to both
native libraries and must stay immutable during a call. The immutable proof
copy and SHA-256 hash are charged inside query time; base64 serialization into
the evidence archive occurs afterwards. Proof byte order is recorded explicitly.

`wide_plan.py`, `wide_descent.py`, and `wide_contraction.cpp` preserve the older
descent arithmetic with a 30-variable bound. Queries with at most 20 variables
continue using the untouched old descent path to isolate the comparison.

## Build, tests and reproducible evidence

From the repository root, using ordinary Python with NumPy installed:

```sh
python3 experiments/groebner-perf-20260924/round20/build.py
python3 experiments/groebner-perf-20260924/round23/build.py
python3 experiments/groebner-perf-20260924/round31/build.py
python3 experiments/groebner-perf-20260924/round32/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round32 -p 'test_*.py' -v
```

On macOS, pass `--metal` to both round31 and round32 builds and set
`QUADRATIC_TEST_METAL=1` for the tests. There are separate optimized, UBSan,
and deliberately small-budget native builds. Tests cover all Boolean
functions on three variables, equation widths through 128, duplicate terms,
spurious linearized roots, high-nullity fallbacks, forged and missing proofs,
incomplete root sets, invalid bases, budget recovery, concurrent calls and
closed workspaces. Nonlinear controls have independently known unique roots
at 21, 24 and 26 variables. Complete 21/24-variable public-point queries also
match an independently exhaustive Python oracle. CI rebuilds on Linux and
macOS; hosted device results are correctness evidence, not physical-host
speedup measurements.

```sh
python3 experiments/groebner-perf-20260924/round32/measure.py --metal --repetitions 31 --output /tmp/branch-run.json.gz
python3 experiments/groebner-perf-20260924/round32/audit.py /tmp/branch-run.json.gz
python3 experiments/groebner-perf-20260924/round32/measure.py --metal --correctness-only --large-controls --repetitions 2 --output /tmp/branch-wide.json.gz
python3 experiments/groebner-perf-20260924/round32/audit.py /tmp/branch-wide.json.gz
```

The small paired study uses nine frozen controls and five arms: the existing
sparse evaluation path, round31 CPU, round32 CPU, round31 Metal, round32 Metal.
Every sample measures one complete public-point query: validation, fresh packed
descent, solving/interpolation, independent exact basis certification, original
equation checks, full-point replay and untouched reference-equation evaluation.
Setup and fixture construction are separately recorded. Warmup and all failed
attempts are retained. Timing eligibility requires the predeclared load bound
at admission, every group start/end and completion; `--correctness-only` is
never eligible. The GPU gate compares each query against the fastest of all
three CPU arms in the same pair and requires actual GPU use and a lower 95%
paired-bootstrap bound above one. Do not interpret hosted CI timings as wins.

The wider controls are correctness-only until the strongest applicable wide
CPU baseline is paired. Their times are diagnostics, not speedup claims.
Source snapshots, compiler/build receipts, native hashes, generated shader
hashes, exact proofs, workloads and an append-only hash-chained journal are
retained. The journal records new immutable proof payloads incrementally.
Mutations to mathematics, proofs, binaries, device use, phase accounting and
source receipts are rejection controls. A failed load admission records zero
timed attempts and must not be overwritten or silently removed.

The source-frozen local correctness run on an Apple M4 Pro passed 29 test
groups and retained 147 complete verified queries: 135 small-control attempts
and 12 wider attempts. The independent audits checked all 106 bound source
files, native build receipts, journals, exact mathematics and curve witnesses.
Representative complete root-coverage records are:

| Frozen control | Fixed branches | Certified impossible | Exhaustively checked residual assignments | Complete roots | Requested Metal behavior |
| --- | ---: | ---: | ---: | ---: | --- |
| 18 variables, field degree 31, seed 101 | 4,096 | 4,090 | 384 | 6 | GPU executed |
| 21 variables, field degree 31, seed 201 | 16,384 | 16,358 | 3,328 | 6 | GPU executed |
| 24 variables, field degree 31, seed 201 | 65,536 | 63,520 | 516,096 | 6 | Explicit CPU shape fallback |

These are exact coverage counts, not wall-time speedup ratios. The wider
controls remain correctness-only. All their roots also matched the separate
full-space Python truth oracle.

## Next hypotheses

1. Measure whether smaller independent proof work outweighs CPU dual-witness
   generation and additional GPU row bookkeeping on complete queries. Keep
   the older paths available for shapes where it does not.
2. Reduce specialization memory traffic using narrow equation words and
   invariant allocation reuse, paired on the same complete-query controls.
3. For surviving branches, test checked rank/nullspace derivations against
   exhaustive residual enumeration. Include adversarial high-nullity and
   spurious-lift cases; a partial lifted solution list is not a certificate.
4. Extend structured certificates to more general F4/F5 derivations only with
   independent ideal-membership and completion checks. The current reduction
   still has exponential `2^x` branching, and worst-case unresolved work is
   `2^(x+y)`. It makes no asymptotic or novelty claim under an “F6” name.
5. After component gains qualify, test their effect in the separately governed
   full single-target IC/rho workflow. Component-only timings cannot answer
   that end-to-end question.
