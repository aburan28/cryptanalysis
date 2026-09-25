# Gröbner performance, second iteration

The 18-variable verification bottleneck is addressed in [../round3/README.md](../round3/README.md). The current dual wrapper adds native verification with an explicit Python oracle option; the round-2 measurements below retain their original source hashes and timing boundaries.

This round retains a faster Rust symbolic preprocessor and stronger, faster
verification in the existing Boolean F4/F5-hybrid runners. It also adds an
opt-in exact Boolean solver and a complete batched Metal RREF prototype.
No worldwide ranking, new universal Gröbner algorithm, pure-F5 correctness
claim, or end-to-end discrete-log speedup is made.

## Retained implementation changes

**Rust F4:** intern monomials when discovered; queue each only once; form the
column set directly from the interned union. The old implementation queued and
sorted copies of every monomial occurrence. The new implementation produces
exactly the same reducer-row multiset and ordered columns as the first round.
Production source: `/Volumes/SSD990/crypto/research/gbrl/src/f4.rs`.

**Boolean verification:** the native and M4RI wrappers now certify the complete
reduced basis from independent exact input zeros and the standard-monomial
dimension. This proves both ideal containments. The previous generator-reduction
check alone could accept an output ideal that was too large. The helper also
canonicalizes ANF by XOR cancellation, instead of dropping duplicate terms.
The runners reuse the certified small zero set during curve replay; they still
check original equations and the elliptic-curve witness. `assignments_checked`
now counts actual inspected assignments; `assignment_search` identifies the
search method.

The default certificate caches monomial truth tables at <=12 variables. An
explicit uncached mode retains only variable truth tables and supports <=20
variables. Both methods are exact and independently tested. They are not
probabilistic checks or assertions based on a solver-provided rank.

**Opt-in Boolean solver:** `boolean_dual.cpp` packs 64 equations per word,
enumerates every Boolean zero using a subset transform, then constructs the
complete reduced grevlex basis with Buchberger–Möller interpolation. These
are established algorithms. The core supports <=24 variables and <=256 roots;
the independently certified wrapper supports <=20 variables. Root-cap failure
returns `inconclusive`, not a partial or incorrect basis. Both subprocess and
in-process library interfaces are available. No numerical basis cache is used.

**Metal:** `batch_rref.metal` performs complete GF(2) rank and RREF, with one
threadgroup per matrix. It keeps matrices on chip, pads the shared stride, and
uses SIMD pivot-search minima. All per-call GPU allocation, copies, submission,
synchronization, and result extraction are charged. Pipeline initialization
is separately reported. This is a standalone throughput prototype; it is not
enabled as the default polynomial solver or a signature-safe F5 reducer.

## Confirmed measurements

All timings are from an Apple M4 Pro on a heavily shared host. Raw samples,
failures, input hashes and build receipts are retained. Medians below are
medians of the five per-target medians; the speedup column is the geometric
mean of paired target ratios, so dividing aggregate medians need not reproduce
that column. These are **PDP/internal algebra stage diagnostics**, not complete
IC candidates or DLP totals.

### Complete PDP queries on five fresh target seeds

`results/query-heldout.json` uses seeds 101–105, 16 recorded solves per arm per
target, one additional retained warmup, and balanced four-arm execution order.
The boundary includes input serialization/marshalling, solving, independent
basis verification, root extraction and curve replay. Instance construction
and compilation are outside this boundary. Every arm returned the identical
canonical basis and the identical first accepted assignment for its target.

| Arm | Median query ms | Paired speedup versus round 1 | Range across five seeds |
| --- | ---: | ---: | ---: |
| Frozen round-1 M4RI hybrid and verifier | 123.604 | 1.00x | — |
| Same hybrid, new exact verifier and root reuse | 94.721 | 1.32x | 1.13–1.59x |
| Evaluation/interpolation, subprocess | 48.456 | 2.62x | 2.39–3.11x |
| Evaluation/interpolation, in-process library | 16.903 | 7.97x | 7.14–10.40x |

The library reuses loaded code. Each of the 85 measured/warmup queries per arm
does fresh numerical solving and verification. `charged_17_query_mean` retains
all warmup and sample costs for each target, including the first library load.
The aggregate charged cost is **12.241 seconds -> 1.939 seconds, or 6.31x**;
the paired geometric mean of the five charged ratios is 6.61x. This is repeated-query
amortization on five frozen targets, not 85 distinct unseen targets. The seeds
were absent from optimization screens. Earlier five-target and intermediate
verifier measurements remain separate, rather than being pooled with this run.

### Core Boolean solve

The separate `results/dual-confirmation.json` confirms the core basis-only
comparison on the five original 12-variable targets, with 7 outer samples and
21 fresh numerical solves per inner sample. Median CPU times were 27.793 ms
for the frozen hybrid and 0.021 ms for evaluation/interpolation; the paired
geometric mean is 1312x. All five systems have six complete roots and every
canonical basis matched. This very large ratio characterizes a tiny workload
where dense elimination is unnecessary; it is not a general F4/F5 speedup.
The complete-query table above is the useful operational comparison.

### Prime-field symbolic preprocessing

`results/preprocess-confirmation.json` contains 63 alternating samples per arm,
each with nine fresh calls. All three versions use identical input S-polynomials;
closure, column equality and round-1/round-2 row-multiset equality are checked.

| Semaev fixture | Original ms | Round 1 ms | Round 2 ms | Versus original | Versus round 1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Polynomial-size parameter 3 | 1.884 | 0.741 | 0.247 | 7.62x | 3.00x |
| Polynomial-size parameter 4 | 1.761 | 0.826 | 0.244 | 7.22x | 3.39x |

These parameters are synthetic polynomial fixture parameters, not canonical IC
`fb<B>` usable-point counts. This table times preprocessing only, not a whole
prime-field F4 solve.

### Batched GPU elimination

`results/gpu-batch-confirmation.json` compares a single CPU thread using M4RI
with Metal. It checks **26,727 matrix outputs and ranks**, including exhaustive
tiny matrices, zero/duplicate rows, pivot gaps, non-word-aligned dimensions,
random batches and matrices captured from the actual Boolean hybrid.

- For batches of 256 synthetic matrices, the four shape-specific ratios were
  3.58–6.68x versus M4RI, with a geometric mean of 4.69x.
- For the five real-matrix batch cases, the geometric mean was 3.58x, with a
  noisy 2.45–8.33x range. Equal-shape cases cycle through the corresponding
  supplied matrices; cases 3 and 4 therefore repeat the same mixed workload.
  They are not five independent throughput trials. The variation is a reason
  to retain the raw samples and avoid promising a stable 8x GPU gain.
- Every single-matrix case lost to M4RI. Most 32-matrix cases also lost.

The real batches repeat captured matrices; they are not 256 complete novel
PDP solves. Polynomial generation, F4 completion, signatures and curve replay
are outside the matrix boundary. The matrix must fit in threadgroup memory;
the current 12-variable Macaulay matrix does not. This experiment supports
continued batching/tiled-backend work, not automatic GPU dispatch everywhere.
CUDA and odd-prime GPU arithmetic are not implemented in this round.

### External and larger checks

`results/external-comparison.json` compares the same complete reduced grevlex
basis against Sage 10.9 / PolyBoRi with default GB options, fresh ideals and a
resident ring. All five 12-variable PDP targets plus planted dense quadratic
systems in 12 and 16 variables matched exactly. The candidate was faster on
these seven cases. This is an exploratory comparison: five sequential PolyBoRi
samples, no OS cache flushing, and no sweep of competing algorithm options.
The 20-variable **whole comparison child** hit its 30-second limit; the child
includes setup, candidate work, and five reference solves. It does not establish
a 30-second lower bound for one PolyBoRi solve.

`results/scaling-probe.json` separately certifies the larger cases without
depending on completion of that reference run:

| Input | Boolean variables | Complete roots | Basis + independent certificate seconds |
| --- | ---: | ---: | ---: |
| Planted dense MQ | 12 | 3 | 0.0076 |
| Planted dense MQ | 16 | 2 | 0.0109 |
| Planted dense MQ | 20 | 1 | 0.1343 |
| Descended PDP, field degree 31, subspace dimension 5 | 15 | 6 | 0.2838 |
| Descended PDP, field degree 31, subspace dimension 6 | 18 | 6 | 3.7886 |

These are single diagnostic executions, not speedup comparisons. Input setup
is separately recorded. The C++ basis stage in the last case was about 3.25 ms;
the independent Python certificate now dominates its verified cost. The process
memory high-water mark is retained, explicitly cumulative across this probe.
No degree of regularity or first-fall degree is inferred from these timings.

The final wrapper was also exercised through curve replay at 15 and 18 Boolean
variables (`results/query-15-variable.json`, `results/query-18-variable.json`).
Both returned `solved` with an independently certified basis and a verified
curve witness. Their single cold-library query costs were 0.364 s and 4.810 s,
with instance setup separately charged at 0.073 s and 0.155 s. In the 18-variable
query, the verifier used 4.700 s while the core basis computation used about
0.913 ms. These single-run diagnostics identify the larger verifier as the next
engineering bottleneck; they are not paired speedup claims.

## Rejected experiments and boundaries

Skipping M4RI's full back-substitution (`ref/`) gave no consistent CPU win.
Generating the matrix from all prepass-reduced generators (`seedmatrix/`)
increased CPU cost substantially. Both remain frozen experiments; neither
was promoted. Literal shared-generator intersection across the five original
targets was zero at all three fixture sizes; `results/shared-generators.json`
retains the negative result.

Files containing `concurrent-screen` ran alongside other experiments from this
task and are excluded from final comparisons. Other screens remain separate
from confirmations. The GPU final run, query confirmation and final core
confirmation were run serially within this task, although unrelated host work
continued. Shared-host timing variability is material.

The “F5” hybrid remains a bounded signature prepass plus ordinary Boolean
completion. Arbitrary RREF of labelled rows does not preserve classical F5
signature invariants. This work does not rebrand that implementation as pure F5.

## Correctness and reconstruction

- 202 fixed/random ideals matched independent Sage/Singular with explicit
  Boolean field equations; both CLI and library outputs matched.
- Independent S-pairs, Boolean field critical pairs, reducedness, source
  reductions and exhaustive root equality passed on those small cases.
- Both certificate modes rejected 550 deliberately wrong candidate bases.
- Undefined-behavior sanitizer checks passed for the C++ executable over the
  same 202-ideal corpus. The separately loaded ordinary library was checked
  for equality but was not itself built with the sanitizer.
- 15 Python tests and 7 Rust F4 tests passed.

From the repository root, use Python >=3.10 for ordinary scripts; this host's
`/opt/homebrew/bin/python3` is suitable. Sage supplies the independent oracle.

```sh
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round2/build.py
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round2/solve_dual.py \
  --n 31 --m 3 --ell 4 --seed 101

DOT_SAGE=/private/tmp/groebner-round2-sage sage -python \
  experiments/groebner-perf-20260924/round2/validate_dual.py

/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round2/query_benchmark.py \
  --seed-start 101 --output /private/tmp/groebner-query-recheck.json

experiments/groebner-perf-20260924/round2/build/batch-rref \
  experiments/groebner-perf-20260924/round2/batch_rref.metal \
  experiments/groebner-perf-20260924/round2/matrices.json
```

Metal execution needs local GPU access; the ordinary sandbox reported no
device, and the actual measurements used the approved local GPU execution
path. No cloud hardware was provisioned. Build receipts bind compiler recipes,
sources, libraries, binaries and input corpora in `results/build-manifest.json`.

See [F6_RESEARCH.md](F6_RESEARCH.md) for the mathematical certificate, conditional
complexity bound, primary literature, and a concrete research hypothesis. The
next asymptotic target is certified switching before degree-driven matrix growth,
with a proof of the controlling structural parameter. Novelty remains unproved.

No complete IC configuration was created here, so no fabricated candidate ID,
usable factor-base count, subgroup size, operation calibration, rho ratio, or
complete DLP total is supplied. Internal Macaulay work belongs to PDP, not the
final relation-matrix LA stage.
