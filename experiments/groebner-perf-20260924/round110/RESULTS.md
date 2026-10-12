# Native seeded-completion results

The seed handoff and proof substitution now execute in C++. The controller lends
the matrix proof view and original packed coefficients directly to the native
continuation API. It builds F4 rows without Python polynomial sets, an exported
Python seed DAG or a repacked coefficient bitset. The independent checker still
checks the returned original-input proof and both directions of ideal membership.

Both hard-query successes from round109 survive in optimized and UBSan modes.
All 26 deterministic records match the Python reference exactly after removing
the separately accounted native scan charge. The basis, continuation proof,
composed proof, checker results and existing logical work counters are identical.
The new raw-input scan adds 33,697 and 34,047 charged work units respectively.
The same 80M total producer/bridge/composition, 20M matrix and 200M checker caps
remain in force; the native path has no looser budget.

| Hard fixture | Native result | Total producer/bridge/composition/scan work | Total checker work | Final proof nodes |
| --- | --- | ---: | ---: | ---: |
| pdp-12-seed-1 | inconclusive | 80,000,000 | 0 | — |
| pdp-12-seed-2 | inconclusive | 79,999,404 | 0 | — |
| pdp-12-seed-3 | solved and replayed | 46,270,023 | 79,023,533 | 73,250 |
| pdp-12-seed-4 | solved and replayed | 41,637,605 | 79,445,824 | 73,397 |
| pdp-12-seed-5 | inconclusive | 79,999,966 | 0 | — |

The other eight fixtures keep their prior successful outcomes. The three
inconclusive cases never return a matrix seed and use the unchanged fresh-F4
fallback. Work units are declared software charges, not CPU instructions.

## Validation

Initial native implementation/build: `117bab33eeb094b6df6842e0a6ca7adf98dee7be`.
Initial complete-query discovery: `28fe16726efa211e97bbdb571d8383c4e5ac394f`.
Full validation and timing source: `5d5fdd8e8c48de4a1dfd6675392ebe9587f86def`.
The first initial build/unit attempt, first discovery and first full validation
all passed. No numerical attempts were discarded or repeated to select results.

An initial continuity helper incorrectly required all rebuilt binary hashes to
match. The optimized binaries match, while the UBSan binary hashes differ; their
source/generated files and all 26 deterministic result records are unchanged.
The cause of the binary differences is not inferred. Initial reference UBSan
bytes were not retained before the rebuild; their commands and hashes remain in
the receipt. All 28 full-validation binaries and both initial continuation
binaries are retained. The failed helper check and corrected comparison remain
in the evidence archive.

Full validation freshly builds 26 reference libraries plus optimized/UBSan native
continuation libraries. The reference's 104 sources, 12 generated files and two
polynomial resources match round109. The F4 engine remains unchanged.

Seven unit-test groups cover 100 randomized nested-multiplication graphs; exact
Python/native proof and partial-work agreement for every small composition work
and node cap; native query work/node exhaustion; empty/repeated outputs; 64-bit
monomials; multi-limb input coefficients; zero/duplicate coefficients and invalid
padding; malformed unused nodes and headers; debug-capture parity; ownership and
concurrent calls. A deliberately forged seed can produce a candidate but is
rejected by the independent checker. Borrowed inputs remain unchanged.

The full workload has 26 rows: 20 algebra verifications, 18 equation/curve replays,
six inconclusive outcomes and no process failures. A native-free audit reproduces
the packed scan charge, compares every result with the frozen reference, then
replays the original-input proof mathematics, Boolean basis certificate, curve
and work/liveness accounting. All 13 coherent artifact corruptions and 16
synthetic publication corruptions are rejected. Synthetic publication controls
are not remote CI receipts.

## Exploratory complete-controller timings

These are median ± median absolute deviation in milliseconds, four observations
per arm after one warmup. The pair order was frozen as AB, BA, BA, AB for every
fixture, with a fresh worker per fixture and a 90-second worker limit. All 130
rows are retained (26 warmups and 104 observations), including 30 inconclusive
outcomes. Every measured result exactly matches the independently audited control.

The interval includes fresh descent/coefficients, solving, checking, diagnostic
proof/continuation materialization, independent equation/curve replay and producer
teardown. It excludes target-independent context/library setup and artifact JSON
encoding/writes. Both diagnostic controllers retain the raw continuation proof;
the native API also supports uncaptured calls, tested separately without a timing
claim. ProducerStats phase-time fields are not populated by this native API;
only its outer elapsed time and logical counters are provided.

| Fixture | Python controller, ms | Native controller, ms | Both outcomes |
| --- | ---: | ---: | --- |
| pdp-6-seed-1 | 3.0881 ± 0.5052 | 2.0512 ± 0.3698 | solved |
| pdp-6-seed-3 | 2.0666 ± 0.1408 | 1.8986 ± 0.0189 | solved |
| planted-dense-mq-12 | 4.9898 ± 0.9807 | 6.1035 ± 2.1079 | gb |
| pdp-9-seed-1 | 8.8487 ± 1.2967 | 9.2656 ± 0.5831 | solved |
| pdp-9-seed-2 | 7.4890 ± 0.2389 | 8.7315 ± 0.4194 | solved |
| pdp-9-seed-3 | 10.3479 ± 1.6650 | 8.2308 ± 1.0050 | solved |
| pdp-9-seed-4 | 7.0546 ± 0.3492 | 8.2702 ± 1.4159 | solved |
| pdp-9-seed-5 | 7.7971 ± 0.1129 | 9.1370 ± 0.9432 | solved |
| pdp-12-seed-1 | 165.4311 ± 33.8144 | 151.3939 ± 21.7154 | inconclusive |
| pdp-12-seed-2 | 196.4058 ± 21.1959 | 210.1679 ± 33.4169 | inconclusive |
| pdp-12-seed-3 | 349.3192 ± 5.1301 | 129.6016 ± 2.0889 | solved |
| pdp-12-seed-4 | 318.5316 ± 23.4147 | 105.6628 ± 2.2995 | solved |
| pdp-12-seed-5 | 182.1160 ± 7.5544 | 173.3099 ± 9.0115 | inconclusive |

The native continuation runs only on the two newly solved hard fixtures. Changes
on the other paths, including regressions, expose controller overhead and host
noise. This macOS ARM64 host lacks the required isolation receipt: every qualified
wall-time and IC speedup remains null. These small planted controls establish no
natural-yield, world-fastest F4/F5, GPU or complete single-target IC/rho result.

## Next work

1. Integrate the native API into the ordinary query object, retaining owned binary
   proof transport and moving diagnostic proof decoding outside the query timer.
2. Profile F4, composition, verification and transport separately to choose the
   next bottleneck from measured phases. Preserve complete-query accounting.
3. Compress matrix witnesses before duplicate pruning passes to test whether the
   other three hard controls can supply useful seeds within the same work cap.
4. Replay matched complete queries on a prepared isolated host before promoting
   timing ratios; continue the GPU single-query crossover and structural F6
   hypotheses under their separate correctness and measurement gates.
