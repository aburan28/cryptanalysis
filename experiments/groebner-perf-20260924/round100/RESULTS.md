# Complete-query frontier results

Executable source: `9bab81acf0ef52d86cd45c6ac6cf6185a41f04b5`. The build binds 64 sources,
18 rebuilt native libraries, two native controls, eleven generated sources
and two regenerated polynomial resources. The producer kernels are unchanged
from round99. All arms now share the existing completion-first, last-use-release
checker; comparisons against earlier legacy-checker timings would conflate
changes. Evidence/documentation commits leave the executed source closure
unchanged.

## Completion outcomes

The two distinct six-variable controls solve at all three work limits. The
nine-variable seed-4 control is inconclusive at 20 million units and solves
at both 80 and 320 million, using exactly 75,513,824 producer work units and
1,408,433 checker work units. Its public fixture target x-coordinate is
1,431,655,760, and the checked Boolean assignment is 20. These are small planted
PDP controls, not recovered DLPs or natural-relation-yield measurements.

The dense twelve-variable algebra fixture, the other four nine-variable PDP
fixtures and all five twelve-variable PDP fixtures remain inconclusive through
320 million units. Their failure reason is the producer work budget. No measured
process timed out or exited unsuccessfully. Every attempt and every budget level
is retained; there is no selected successful subset or adaptive retry timing.

## Complete solved-query costs

Milliseconds below are median ± median absolute deviation over three frozen
observation calls, each in a fresh worker. Startup, fixture/layout preparation
and artifact storage are outside the target-dependent interval and recorded
separately. Fresh descent, production/certification, proof materialization,
extraction, independent equation/curve replay and teardown are included.

| Fixture | Producer limit | Original sorter | Packed keys | Radix | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| pdp-6-seed-1 | 80000000 | 4.565 ± 0.034 | 4.430 ± 0.001 | 4.346 ± 0.128 | solved |
| pdp-6-seed-3 | 80000000 | 3.962 ± 0.013 | 4.035 ± 0.042 | 4.094 ± 0.056 | solved |
| pdp-9-seed-4 | 80000000 | 83.934 ± 0.429 | 81.451 ± 0.419 | 83.630 ± 0.385 | solved |
| pdp-9-seed-4 | 320000000 | 80.662 ± 0.020 | 79.782 ± 0.213 | 80.820 ± 0.029 | solved |
| pdp-12-seed-1 | 320000000 | 418.081 ± 4.240 | 290.702 ± 0.185 | 253.429 ± 1.508 | inconclusive |

The completed nine-variable query has no consistent radix gain. At the
80-million limit its original producer median is 48.756 ms and its independent
checker median is 29.821 ms; at the 320-million limit these are 47.906 ms and
27.610 ms. The checker remains a substantial cost despite using many fewer
logical work units. Operation counts are not interchangeable with wall time.

The twelve-variable row shows lower local time to an unchanged failure. It
does not establish faster completed queries. This host lacks a qualifying
isolation receipt, so qualified, aggregate and online speedups remain null.
All raw phases, worker elapsed times and process peak RSS are retained.

## Independent verification and memory

The completed nine-variable proof has 8,415 nodes. Independent liveness
reconstruction matches the native checker: 11,630 peak live terms, 561,586
released terms, all 8,415 nodes released, and 33,660 metadata bytes. The two
budget levels produce the same certificate. Three unique proof blobs cover
the three completed mathematical fixtures. Deduplication happens only when
writing artifacts, after every fresh solve and certificate check.

All seven test groups pass, including legacy/live-checker agreement, exact
budget behavior, changed targets, concurrency, native radix controls, proof
blob storage and real subprocess failure/deadline handling. The native tests
retain 16,384 multiplication and 1,728 sorting cases per optimized/UBSan build.

The control audit passes all 234 calls: 48 independently certified/replayed
PDP results, 186 unsuccessful calls, 156 exact trace pairs and 48 reconstructed
proof lifetimes. The preset diagnostic audit passes all 468 calls (117 warmup,
351 observations): 96 certified/replayed results, 372 unsuccessful calls,
312 exact trace pairs and 96 reconstructed lifetimes. Both have zero external
execution failures. All 33 corruption controls are rejected, including a
self-consistently rehashed forged proof.

## Next decision

Keep sorting variants opt-in. Test the existing reusable Macaulay layout path
against this completed-query baseline, with fresh coefficients and row values
for every target, unchanged independent checking and all fallback work charged.
The goal is to reduce repeated symbolic construction/elimination rather than
further optimize sorting that did not materially help this completed case.
A denser independent derivation representation is a separate possible target
for the remaining checker cost; neither hypothesis is a measured gain here.

Qualify any resulting completed-query improvement on an isolated CPU host
before promotion. This component panel does not establish an additional 2×
gain, a complete single-target IC/rho result, a GPU crossover, globally fastest
F4/F5 or a new asymptotic F6 algorithm. The broader goal remains open.
