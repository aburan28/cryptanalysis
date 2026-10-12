# Early proof compression retains all five hard seeded F4 candidates

The early parity rewrite brings each of the five frozen 12-variable
point-decomposition matrices below the unchanged 20-million matrix-work cap.
Their retained proofs feed native seeded F4, yielding five independently
certified Boolean bases and five successful curve replays in both optimized
and undefined-behavior-sanitized builds. With the previous late rewrite,
seeds 1, 2, and 5 used the 80-million shared producer budget and returned
`inconclusive` after a fresh F4 attempt. Across all thirteen frozen cases and
both builds, early mode produced 26 algebra certifications and 24 curve
replays; late mode produced 20 and 18 respectively. All 52 numerical workers,
the independent audit, five native unit groups, and thirteen artifact
corruption controls passed.

The point-decomposition controls use the fixed 31-bit binary field represented
by modulus `2147483657` (`x^31+x^3+1`), curve coefficient `b=1`, and three
summands. The 6-, 9-, and 12-variable cases use summand subspace dimensions
2, 3, and 4 respectively; the separately named dense Boolean MQ case has
12 variables. Each seed fixes its equations, target abscissa, and workload
digest in `panel/report.json`. These are planted decomposition correctness
controls, so their yield is not an estimate of ordinary relation yield.
Each mode receives the same input and limits: 20,000,000 matrix work,
80,000,000 shared producer work, 200,000,000 checker work, 2,000,000 proof
nodes, 2,000,000 live checker terms, 4,096 rows, and a 64-row batch. Failed
matrix attempts and fresh F4 fallbacks remain charged.

Optimized 12-variable records (work units; `new` selects early parity):

| Seed | Late result | New result | New matrix work | New total producer work | Final proof nodes |
|---:|---|---|---:|---:|---:|
| 1 | inconclusive at producer cap | certified; curve replay | 19,872,703 | 41,399,086 | 72,139 |
| 2 | inconclusive at producer cap | certified; curve replay | 19,551,005 | 39,736,180 | 70,454 |
| 3 | certified; curve replay | certified; curve replay | 18,893,771 | 45,420,758 | 73,250 |
| 4 | certified; curve replay | certified; curve replay | 18,801,235 | 40,795,304 | 73,397 |
| 5 | inconclusive at producer cap | certified; curve replay | 19,205,139 | 43,000,957 | 73,195 |

Each successful final proof replays from original equations in an independent
Python integer model, then passes the Boolean basis certificate and curve
replay. The native-free audit also replays every matrix work counter and the
strict accepted-size bound `compressed_nodes < active_nodes <= ordinarily_reachable_nodes`.
It loaded no candidate native binary. The thirteen mutation controls reject
corrupted size bounds, selection flags, work charges, basis and certificate
fields, curve results, and modified proof bytes even with a recomputed digest.

Paired complete-query profiling used one warmup and four AB/BA/BA/AB
observations per mode and case: 26 warmups and 104 measured observations.
Every non-timing result field and proof byte digest matched its independently
audited validation row. The interval begins with fresh target coefficient
descent and ends after native matrix production, bounded F4 continuation or
fallback, independent certificate verification, solution extraction, both
equation/curve checks, proof copying and lease teardown. Reusable layouts,
fixture construction, process launch, and artifact serialization are outside
the interval. The following medians ± median absolute deviation are in
milliseconds on a contended macOS ARM64 host, so their qualified CPU speedup
is unknown (`null`); they are useful as phase diagnostics and retain all
regressions.

| 12-variable seed | Late query | Early query | Early matrix | Early native continuation | Early checker |
|---:|---:|---:|---:|---:|---:|
| 1 | 192.243 ± 17.287 | 162.076 ± 5.511 | 26.938 | 76.140 | 37.064 |
| 2 | 188.937 ± 22.382 | 110.809 ± 15.351 | 35.418 | 39.351 | 27.004 |
| 3 | 103.193 ± 11.927 | 119.675 ± 14.979 | 21.325 | 65.554 | 19.726 |
| 4 | 165.033 ± 20.575 | 81.155 ± 22.774 | 18.586 | 39.852 | 13.972 |
| 5 | 198.152 ± 41.316 | 136.115 ± 8.874 | 35.177 | 67.168 | 25.201 |

The native continuation column still combines input preparation, F4,
proof packing, composition, and finalization. A follow-on opt-in phase
instrumentation experiment separates those costs and preserves the same
certificates and deterministic counters. The resulting matched complete-query
comparison can then be replayed on the isolated Linux benchmark service for
a controlled CPU timing ratio. Single-query GPU work measures target-dependent
system construction, transfer, launch, synchronization, result checking, and
curve replay; the structural separator prototype checks the actual equation
width before choosing a bounded-width path.

Validation used source commit `e27ed70901e9bbedf988f7f5f41806c810794322`
and tree `5911e69ca41bf5a5ee51cb75db10244850e3009f` with Python 3.13,
Apple clang 17, macOS 26.6 ARM64, and source-matched existing round108/110
reference libraries. The successful local run is `early-parity-validation-v4`;
`early-parity-profile-v3` is its source-matched profile. Earlier records are
preserved: the first independent audit stopped after 42 of 52 rows, the
queued validation stopped before its first step, and a later validation
failed four Python 3.9 compatibility checks because that interpreter lacks
`int.bit_count`. They are not counted as passing runs. `results.tar.gz` and
`archive.json` provide the lossless content-addressed raw evidence, including
these interrupted and failed attempts, exact source/build receipts and
proof artifacts. The archive recipe is `archive.py`.
