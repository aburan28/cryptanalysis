# Complete-query evidence

Executable source: `e705549e224f238eeca295d953bc15d1104f8aa4`.
The retained build binds 51 sources, 12 freshly compiled native libraries,
five generated native/reference sources, and two freshly regenerated
summation-polynomial resources. Later commits add documentation and evidence
without changing that executable source closure.

## Correctness and outcomes

Seven integration test groups passed across optimized and UBSan builds.
They cover live input transport without repacking, lease lifetime and thread
ownership, changed targets with reused storage, exhausted budgets, corrupt
descent coefficients, and extraction/final curve replay failures. The first
development test incorrectly assumed seeds 1 and 2 gave different six-variable
targets; they are identical. The test was corrected to use seed 3 after checking
the actual target coordinates. Its original failure log is retained.

The full correctness panel contains 184 calls: 23 fixtures, four checker arms,
and two build modes. It has 80 certified algebra outputs, including 40 solved
PDP calls, and 104 unsuccessful calls. The native-free audit verified seven
distinct mathematical outputs, 138 paired producer traces, 60 successful
checker-counter pairs and 40 proof lifetimes. All 32 artifact corruption
controls were rejected.

The single preset diagnostic panel contains 552 calls: 184 warmup calls and
368 observation calls. All raw outcomes remain in the archive. Its audit
verified 414 paired producer traces, 180 successful checker-counter pairs and
120 proof lifetimes. No diagnostic reruns were selected to improve timings.

Each arm certifies the same ten fixtures: the random eight-variable control,
four easy wide algebra controls, and all five six-variable planted PDP
fixtures. Those five PDP fixture labels represent only two distinct targets;
seeds 1, 2, 4 and 5 share the same point. The remaining thirteen fixtures
(three dense MQ and all ten nine-/twelve-variable PDP fixtures) exhaust the
20-million-operation producer budget before any checker is invoked. They
are inconclusive results, not solved targets or speedup wins.

## Local timing is not a controlled speedup

Selected complete-query wall times below are milliseconds, median ± median
absolute deviation over four preset observation calls. Each successful PDP
interval includes fresh descent, native solving/certification, proof export,
bounded extraction, independent equations/curve replay, and lease teardown.

| Fixture | Outcome | Legacy | Completion first | Release, cumulative limit | Release, live limit |
| --- | --- | ---: | ---: | ---: | ---: |
| PDP 6, seed 1 | solved | 7.341 ± 3.223 | 4.454 ± 0.493 | 7.711 ± 3.741 | 3.950 ± 0.080 |
| PDP 6, seed 3 | solved | 4.583 ± 0.632 | 3.805 ± 0.054 | 10.216 ± 3.578 | 4.273 ± 0.485 |
| Random 8 | certified basis | 52.066 ± 7.308 | 50.247 ± 19.470 | 39.687 ± 9.790 | 38.201 ± 12.432 |
| PDP 9, seed 1 | inconclusive | 80.587 ± 28.240 | 69.724 ± 29.471 | 31.242 ± 11.687 | 18.525 ± 0.217 |

The last row is a useful warning against attributing this host's timing
differences to the checker: every arm performs exactly the same producer work
and none invokes a checker. The local lock excludes our cooperating heavy jobs;
it does not establish host-wide CPU isolation. All qualified, aggregate, and
online speedup fields remain null. The table does not support a 2× claim or
selection of an automatic routing policy. Every fixture's raw timings, phase
costs, medians, deviations and ranges are in `summary.json`.

## Exact storage diagnostics

These counters describe stored proof-polynomial terms, not RSS or total
allocations. Cumulative retention counts every computed proof value; the live
peak includes a newly computed value before its parents can be released.

| Certified fixture | Cumulative proof terms | Peak live proof terms | Use-count metadata bytes |
| --- | ---: | ---: | ---: |
| PDP 6, seed 1 | 7,812 | 309 | 2,652 |
| PDP 6, seed 3 | 3,289 | 212 | 1,432 |
| Random 8 | 74,843 | 1,527 | 17,288 |
| Pair products 64 | 442 | 192 | 884 |

Every live proof value is released after its final use. The independent oracle
reproduces those lifetimes and both ideal-inclusion/completion obligations.
The producer, accepted basis, derivation DAG and mathematical checker counters
agree across arms, allowing for the explicitly counted liveness-planning work.

## Scope

This is a component integration and planted correctness study. There is no
complete candidate manifest, ordinary relation-yield experiment, recovered
discrete logarithm, paired rho result, or high-regularity asymptotic claim.
Candidate and online-speedup fields remain null. Wide easy Boolean systems
demonstrate certificate width support without establishing difficult-system
solving performance. Root extraction here remains bounded enumeration on the
small planted fixtures.
