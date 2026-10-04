# Shared producer coefficient transform: complete-query results

Source `a357a2bf7874f92f7fd02ac703362f40c4854dc7` completed the full
validation on 2026-10-04, on a physical Apple M4 Pro, 14 CPU cores, ARM64,
48 GiB RAM. The producer transforms fresh packed ANF coefficients in its
existing Metal buffer and reuses that invocation's transformed table for
projection. The independent round66 checker keeps its own implementation,
original-input reconstruction, buffers and proof checks. CPU transform
remains the default; stagewise and tiled Metal modes are explicit options.

## Exact validation

| Control | Result |
| --- | --- |
| Shared-buffer native controls, optimized | 192 pass |
| Shared-buffer native controls, UBSan | 192 pass |
| Injected pipeline-setup failure, UBSan | 192 pass |
| Full producer API test groups | 8 pass |
| Complete queries across 18 frozen inputs, 6–27 variables | 732 verified |
| Unsupported planned cells | 24 retained; no query executed |
| Rejected explicit GPU setup requests | 8 retained; each attempted and timed once |
| Independent original-ANF replay | 35 distinct proofs and exact Boolean bases pass |
| Balanced complete-query diagnostic | All 576 fresh queries verified |
| Retained source, input, generated and native bindings | 639 checked |
| Executed source/input bindings to frozen Git blobs | 411 checked |
| Downloaded native binaries loaded by artifact auditor | None |

The 756 planned query records cross producer/checker backends, optimized and
UBSan builds, transform modes and serial/prepared/overlapped verification.
The explicit GPU transform supports at most 32 equations. Eight setup requests
on the 83-equation control therefore fail, each making three preparation
schedules unavailable. Those 24 cells have no query time and are not wins or
three separate attempts. The same wide control succeeds through the portable
CPU path and the Metal backend's existing CPU fallback. CPU-only validation
has 108 complete queries. CI rebuilds native code independently on Linux and
macOS and records actual device availability.

The reference and candidate factories are separate: the reference loads the
unchanged round51 producer; the candidate loads round68; both use round66's
independent checker. Validation asserts these binary paths and compares exact
bases, proof bytes, assignments and legacy logical counts. API controls cover
equation widths 1–128, fresh reuse, malformed proofs, partial/projection
configuration, native input failures, post-GPU proof-budget failures,
concurrent calls and owner lifetime. Native buffer controls reject stale or
consumed generations, wrong pointers/extents, private or untracked storage,
and mismatched devices. Failed configuration preserves the previous usable
mode while revoking readiness. UBSan instruments host code; exact comparisons
provide GPU correctness evidence.

An earlier frozen validation stopped on accounting for the wide-equation CPU
fallback. No timing panel ran from that snapshot. Its partial journal, failure
state and validation log remain indexed and retained. A preliminary unfrozen
smoke run also used a candidate factory as its reference; it is explicitly
excluded from unchanged-producer equivalence evidence. The corrected source
was rebuilt and the entire validation rerun. `prior-attempts.json.gz` records
both limitations.

## Exploratory complete-query panel

The producer backend is Metal in all eight arms. Each checker (CPU or SIMD
Metal coefficient transform) is paired with the unchanged producer, the new
producer in CPU-transform mode, or either GPU-transform mode. The eight-order
Williams block balances positions and all 56 ordered neighboring pairs and
repeats three times, giving 24 observations per arm/input. Every observation
freshly solves and independently certifies the basis, checks original
equations and replays the public point. Per-query conversion, copies and
synchronization are charged. Reusable contexts, allocation and pipeline setup
are recorded separately. There is no shared answer cache.

Medians of `result.complete_query_ns`, in milliseconds:

| Input variables | Checker transform | Unchanged producer | New CPU transform | Stagewise Metal | Tiled Metal |
| ---: | --- | ---: | ---: | ---: | ---: |
| 18 | CPU | 1.741688 | 2.056312 | 1.941688 | 1.852625 |
| 18 | SIMD Metal | 2.043334 | 1.969041 | 2.179855 | 2.256458 |
| 24 | CPU | 13.293000 | 13.521501 | 12.891479 | 12.738750 |
| 24 | SIMD Metal | 12.494125 | 12.247937 | 11.515812 | 11.318896 |
| 27 | CPU | 115.592062 | 115.693770 | 106.690833 | 105.297188 |
| 27 | SIMD Metal | 107.930833 | 110.837208 | 98.116896 | 97.159083 |

Inputs are `n31-m3-ell6-seed101`, `n31-m3-ell8-seed201` and
`n31-m3-ell9-seed201`. The raw outer call times are also retained; the
largest tiled/SIMD arm has a 97.199687 ms outer median. Context setup stays
outside both intervals. The smallest SIMD-checker case regresses with the
GPU producer transform. CPU-control fluctuations also remain visible.

The host was heavily contended: one-minute load ranged from 29.4868 to 34.1060.
There is no host-isolation receipt. Every timing is exploratory,
`timing_eligible` is false, and aggregate speedup is unknown. These observations
do not establish a controlled GPU crossover or justify automatic routing.
`paired-diagnostics.json.gz` retains all within-trial differences for 18
comparisons, with 10,000-resample percentile intervals (seed 680067). They
describe uncertainty conditional on this sample; they do not model uncontrolled
host effects. `summary.json.gz` retains medians, IQRs and nested profiles.

For the tiled producer with the SIMD Metal checker, paired candidate-minus-
reference differences are:

| Input variables | Median paired difference (ms) | Conditional descriptive 95% interval (ms) |
| ---: | ---: | ---: |
| 18 | +0.455855 | [+0.094083, +0.784834] |
| 24 | −1.321896 | [−1.908042, −0.804458] |
| 27 | −10.062125 | [−12.346834, −9.017417] |

The median of paired differences need not equal the difference of the two
arm medians. These intervals carry the same shared-host limitation above.

## Next engineering target

For the largest tiled/SIMD arm, nested medians are 55.2804 ms for the producer
and 41.6154 ms for independent checking. The producer's specialization is
7.8167 ms and its evaluation is 42.3904 ms. The checker spends 16.3107 ms on
multiplier identities, 11.8622 ms on residual enumeration, 10.2339 ms on
specialization and 2.1660 ms on constant identities. These are nested or
separately summarized intervals; do not add their medians into a total.

The next experiment should accelerate exact independent affine-multiplier
checking. Preserve reconstruction from original ANF, fresh proof input,
all Boolean coefficient identities, CPU fallback and adversarial rejection.
Start with a standalone bounded kernel and exact CPU oracle. A GPU version
must charge proof upload and result synchronization, report actual work if
parallel execution runs past the first failing record, and then pass the full
query and original-ANF audits. Residual enumeration and producer evaluation
remain separate targets if this kernel does not improve complete queries.

For a structural F6 experiment, replacing more residual enumeration with
certified affine elimination could reduce instance-specific work. It requires
explicit applicability conditions and controls that defeat those conditions;
it is not yet an algorithmic or asymptotic result. General F4/F5 comparisons
and a fully charged, independently verified single-target IC/rho comparison
remain separate acceptance gates. These query controls do not estimate natural
relation yield, recover a discrete logarithm, or establish a global speed rank.

## Retained evidence

`results/` includes raw diagnostic rows and order, setup costs, all correctness
metadata, proof hashes, source/native receipts, original-ANF audit, failure
records and logs. The compact correctness metadata omits proof payloads and
cannot independently replay them. The full proof bundle and native artifacts
are indexed by SHA-256 and size in `retained-artifacts.json.gz`, rooted at
`/Volumes/SSD990/llm/tmp/cryptanalysis-groebner-recovery-20261004/shared-producer-integration-v2`.
The local index also covers the separately rebased pure-Python replay bundle.
The dedicated CI workflow rebuilds and regenerates the full artifacts on each
platform and retains them for 14 days. A hosted CPU run or unavailable Metal
device is not physical GPU validation.
