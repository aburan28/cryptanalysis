# Packed monomial-order results

Executable source: `4bb6ef6d5971fdc9537567f5df94d5ceac9e40fa`. The build binds 58 source files,
18 rebuilt native libraries, two native control executables, eleven generated
sources and two regenerated polynomial resources. Evidence/documentation
commits leave the executed source closure unchanged.

## Correctness and failure preservation

All six Python test groups pass on optimized and UBSan builds. Native controls
compare 32,768 multiplication cases per build against the unchanged source
method, including partial budgets and proof-node exhaustion. The order test
checks 1,049,088 pairs per build plus complete sorted-vector comparisons.
Controls cover constants, cancellation, bit 56, bit 57, bit 63, all-bit masks,
wide fallback, public-API proof agreement, changed targets and concurrency.
A standalone test initially resolved the wrong historical audit module; the
import ordering was fixed before freezing, and that failure log is retained.

The native-free artifact audit passes 184 control calls: 138 exact trace pairs,
69 sorting-counter records, 80 certified algebra outputs, 40 solved PDP calls
and 104 unsuccessful calls. The one preset diagnostic run passes 552 calls
(184 warmups and 368 observations), 414 exact trace pairs, 240 certified algebra
outputs, 120 solved PDP calls and 312 unsuccessful calls. Seven distinct
mathematical outputs are independently rechecked. All 26 corruption controls
are rejected. Every accepted proof, assignment and equation/curve replay is
unchanged; every work-limit failure is retained.

## What the keys change

For PDP 12 seed 1, all 2,844 ordered-multiple sorts, covering 1,140,509 terms,
qualify for both key policies. The candidate computes each degree once when
encoding; subsequent sort comparisons are unsigned integer comparisons.
The 32-term threshold selects no sorts for either solved six-variable target
or the random-eight control. It selects 935 of 4,023 sorts on PDP 9 seed 1.
This illustrates why a single sorting policy need not help every workload.

## Local complete-query diagnostics

Milliseconds below are median ± median absolute deviation from four frozen
observation calls. All rows and phases, including failures, are retained in
`summary.json` and the archive. Successful PDP timing includes fresh descent,
native solving/certification, proof materialization, extraction, independent
equation/curve replay and lease teardown; reusable setup stays separate.

| Fixture | Outcome | Baseline | Comparator control | Keys | 32-term threshold |
| --- | --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | solved | 6.200 ± 0.501 | 5.318 ± 0.765 | 5.272 ± 0.417 | 5.171 ± 0.248 |
| pdp-6-seed-3 | solved | 8.828 ± 0.585 | 7.945 ± 1.643 | 5.351 ± 1.444 | 5.264 ± 0.877 |
| pdp-9-seed-1 | inconclusive | 18.657 ± 0.338 | 18.244 ± 0.313 | 18.126 ± 0.311 | 18.383 ± 0.540 |
| pdp-12-seed-1 | inconclusive | 55.263 ± 0.344 | 55.768 ± 0.112 | 44.129 ± 0.672 | 43.816 ± 0.492 |
| random-8-budget-control | gb | 25.947 ± 0.369 | 26.732 ± 0.498 | 26.548 ± 0.174 | 26.263 ± 0.185 |

The host has no qualifying isolation receipt. Small solved controls show
substantial dispersion, including the comparator/threshold arms that use the
original sorting operation. No selected rerun replaces these observations.
All qualified, aggregate and online speedups remain null. The lower local
cost on the twelve-variable fixture is time to the same inconclusive result,
not a verified solved-query win. The random-eight result does not improve.

## Next decision

Keep this candidate opt-in. Qualify the promising larger-row effect with
isolated paired CPU measurements before changing dispatch. A bounded radix
sorter over these integer keys is the next concrete hypothesis: it could
replace comparison sorting for sufficiently large rows, but extra passes and
scratch traffic may lose on small rows. Freeze its cutoff and memory cap
before measurement; preserve exact traces, wide fallback and inconclusive
cases. This proposal is not implemented in round98.

This is a generic algebra/planted-PDP component experiment. Five six-variable
fixture labels contain only two distinct targets. There is no ordinary
relation-yield estimate, complete recovered DLP, paired rho result, GPU
crossover or new asymptotic Gröbner algorithm. Key packing itself retains
comparison sorting and does not establish an F6 result.
