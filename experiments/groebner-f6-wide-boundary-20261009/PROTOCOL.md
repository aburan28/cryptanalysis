# Exact wider-boundary F6 experiment

This experiment extends the target-affine S3 separator to seven cases beyond
the earlier 21-variable policy cap. It tests whether widening the **admitted
local bag** to 22 or 23 variables, with a fixed 200,000,000-state construction
limit, gives complete exact target answers while retaining the independent
curve-sum and original-equation checks. A boundary case at bag width 21 is
also included. The source and workload are frozen before the exhaustive run.

## Mathematical and resource scope

Work over the binary field represented by the checked `GF2n(9)` code, the
checked binary curve with `b=1`, and the checked S3-chain fixture with seed 1.
For each summand the allowed abscissae are integers `0 <= x < 2^ell` in that
field representation. The finite target workload is every one of the 512
abscissae in the field, in ascending order. The independent comparator lifts
every allowed summand abscissa to all curve points with that abscissa,
including distinct negatives, takes all `m`-fold curve sums, and records the
finite final abscissae. Fixture generation and this comparator are outside
the per-query interval.

The seven admitted `(n, m, ell, seed, max_bag)` cases are:

| Field bits | Summands | Summand bits | Seed | Max bag |
| ---: | ---: | ---: | ---: | ---: |
| 9 | 4 | 4 | 1 | 22 |
| 9 | 5 | 4 | 1 | 22 |
| 9 | 6 | 4 | 1 | 22 |
| 9 | 4 | 5 | 1 | 23 |
| 9 | 5 | 5 | 1 | 23 |
| 9 | 3 | 6 | 1 | 21 |
| 9 | 3 | 7 | 1 | 23 |

All seven run both optimized and undefined-behavior-sanitized native builds.
For each target, the compact separator and the bitplane target-affine
separator run in alternating order. Each arm receives a fresh target-specific
query; they share only target-independent static factors and affine template
planes within one case. A satisfiable answer is checked against the original
chain ANF equations and replayed as a curve-point sum. Assignments need not
be identical because the same target can have multiple decompositions.

The four rejection controls are `(m, ell, max_bag, expected status)` =
`(4,4,21,width-cap)`, `(5,5,22,width-cap)`, `(4,6,24,state-cap)`, and
`(4,7,24,width-cap)`, all with `n=9`, seed 1, and the same state limit. They
record the boundary of the applicable structural regime. The algebraic
non-affinity control `u0*u1*x0` has zero at target 0 and at both basis targets
but one at target 3; it must disagree with affine reconstruction.

The final S3 equation is affine in the target **bits** in characteristic two:
with static symbolic `a,b`, `S3(a,b,z) = a^2 b^2 + (a^2+b^2)z^2 + ab z + b_curve`.
Squaring and multiplication by fixed field elements are linear over GF(2).
Thus the coefficient vector at target `u` is exactly its zero-target vector
XOR the basis-target deltas selected by the bits of `u`. This is the
applicability argument for reusing the separator and target truth planes.
It requires the target to occur through this affine form; the non-affinity
control prevents extending the argument to a generic target equation.

## Acceptance and accounting

The run passes only if all 7 x 2 x 512 = 7,168 matched target pairs complete,
each of their 14,336 arm statuses agrees with the independent curve-sum
comparator, every satisfiable arm passes both original-equation and point
replay, all four cap controls return their frozen status, and the non-affinity
control differs at target 3. A failure, timeout, exception, or missing row
remains in the JSONL journal and fails the run. Both native build receipts,
their binary hashes, the executed dependency sources, the new driver sources,
and the frozen commit are checked and stored in the compressed report. The
report is written after each case; the journal flushes after every arm.

`setup_ns` includes Python fixture-dependent construction, affine template
construction, and both native static layouts. `online_ns` for an arm starts
before target-specific native preparation and stops after independent ANF and
curve-point checks. These values are diagnostics on the execution host.
`timing_eligible=false` and `qualified_speedup=null` until a matched,
complete-query isolated-host panel satisfying `docs/ISOLATED_BENCHMARKS.md`
exists. The panel is a point-decomposition stage experiment, not a
single-target index-calculus measurement. GPU conversion, transfer, launch,
synchronization, and replay remain separate acceptance costs for a CUDA
crossover experiment.

## Reproduction

From a clean full checkout at the committed source snapshot, build the
source-bound predecessor chain in `.github/workflows/groebner-f6-wide-boundary.yml`
and run:

```sh
python3 experiments/groebner-f6-wide-boundary-20261009/validate.py \
  --output /absolute/path/to/new-evidence-directory
```

`--runtime-root /absolute/path/to/byte-identical-built-checkout` permits
reuse of already-built binaries when working from a sparse source checkout.
The driver verifies source identity and binary receipts before the run.
