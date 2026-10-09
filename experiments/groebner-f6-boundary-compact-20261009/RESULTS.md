# Compact F6 separator boundary: exact result

The compact query engine removes 18 static-only variables from the fresh-target
elimination ring while preserving the original factor truth tables and witness
reconstruction. On the frozen four-summand S3 system over GF(2^9), 90 small
random systems agreed with exhaustive Boolean solving in optimized and UBSan
builds, six selected S3 targets agreed in both builds, and all 512 target
abscissae agreed with the independent packed-factor reference. Satisfying
assignments passed every original ANF equation and curve-point replay.

The source was frozen at `abbd2477acd23b147f0f7915277c016f5f500933`
before building or timing. [The build receipt](evidence/build-receipt.json),
[512-target semantic replay](evidence/semantic.json), and
[paired raw report](evidence/paired-report.json) retain binary hashes, exact
answers, phase counters, failures, order, and individual timings. The local
macOS ARM64 host was shared and heavily loaded, so these timings are
exploratory; `timing_eligible` and `qualified_speedup` remain false and null.

| Target abscissa | Status | Paired compact/message online ratio, median of five | Paired range |
| ---: | --- | ---: | ---: |
| 0 | satisfiable | 0.995 | 0.887–1.082 |
| 1 | satisfiable | 1.009 | 0.969–1.094 |
| 2 | unsatisfiable | 0.953 | 0.925–1.116 |
| 9 | unsatisfiable | 0.945 | 0.878–0.972 |
| 100 | unsatisfiable | 1.027 | 0.871–1.099 |
| 511 | unsatisfiable | 0.949 | 0.885–1.062 |

The six cell-median ratios have a geometric mean of 0.979. The complete
per-target interval starts before fresh S3 equation construction and ends
after independent ANF and point verification. It includes Python packing,
native factor construction, elimination, and any result reconstruction.
One warmup and five alternating matched pairs were recorded for each target.
Median native elimination time over the measured rows was 0.0983 ms for the
message reference and 0.0917 ms for the compact engine. The SAT controls
remove 18 eliminations; across the selected mixed-status queries the median
reported logical state charge changes from 4,265,508 to 4,265,472. Static
setup, which cached 19,004,432 factor states and 4,257,792 elimination
states for both arms, is recorded separately in the raw report.

The smaller ring provides a correct structural reduction, but the local
complete-query difference is too small and variable to promote. The next
implementation experiment should avoid rebuilding the same target-independent
S3 coefficients in Python on every query, then compare complete queries on
the same frozen targets. A controlled CPU timing claim still requires a
qualifying [isolated-host receipt](../../docs/ISOLATED_BENCHMARKS.md).
