# Affine S3 target compilation reduces local complete-query time

Compiling the target-independent S3 coefficients once preserves every exact
answer while reducing fresh target-equation construction. In the frozen
four-summand chain over GF(2^9) with modulus `515`, the candidate matched 612
direct S3 equation constructions across field widths 4, 6, and 9, passed six
S3 target controls in optimized and UBSan builds, and agreed with the
independent packed-factor reference on all 512 target abscissae. Every
satisfying assignment passed original-equation and curve-point replay.

Source commit `db958538cfed58cfe688434f75a4a88733814a5c` was frozen before
building, validation, and timing. The [build receipt](evidence/build-receipt.json),
[512-target semantic replay](evidence/semantic.json), and
[paired raw report](evidence/paired-report.json) retain source and binary
hashes, exact outputs, failures, paired order, and phase timings.

| Target abscissa | Status | Median paired affine/compact complete-query ratio | Paired range |
| ---: | --- | ---: | ---: |
| 0 | satisfiable | 0.808 | 0.482–0.920 |
| 1 | satisfiable | 0.866 | 0.764–0.963 |
| 2 | unsatisfiable | 0.660 | 0.270–0.979 |
| 9 | unsatisfiable | 0.624 | 0.538–0.785 |
| 100 | unsatisfiable | 0.731 | 0.672–0.825 |
| 511 | unsatisfiable | 0.699 | 0.617–0.793 |

The geometric mean of the six cell-median ratios is 0.727. Each cell has one
warmup and five alternating matched pairs; all 72 executions, including
warmups, completed and matched the frozen independent answer. The online timer
starts before constructing the target-dependent ANF rows and ends after the
native solve, independent original-equation check, and point replay. Context
creation and target-independent lookup tables are outside that interval and
recorded separately. The candidate's median ANF construction time over the
30 measured runs was 0.0154 ms; the median native-wrapper solve was 0.1812 ms.
The compact reference's median native-wrapper solve was 0.1806 ms, so the
observed difference lies in target preparation, as intended.

These measurements ran on a heavily loaded shared macOS ARM64 host. Their
paired spread is material; `timing_eligible` is false and
`qualified_speedup` remains null. A controlled CPU result needs the matched
complete-query panel on a physical host passing the repository
[isolation contract](../../docs/ISOLATED_BENCHMARKS.md). The implementation
is opt-in and preserves the compact engine as its reference. The next F6
kernel question is whether the target-dependent factor can be constructed
from the affine template inside the native boundary, removing Python packing
without changing its exact equations or witness checks.
