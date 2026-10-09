# Reused packed ANF buffers reduce local fresh-target query time

The direct packed path fills reusable offsets and monomial-term arrays from
fresh S3 target coefficients and passes them to the native compact separator.
It avoids constructing Python row sets or lists and avoids per-query ctypes
repacking. On the frozen four-summand GF(2^9) chain (modulus `515`, curve
coefficient `b=1`, three factor-base bits per summand), it matched 612 direct
S3 equation constructions at widths 4, 6, and 9, passed six optimized and
UBSan target controls, and agreed with the independent packed-factor reference
on all 512 target abscissae. The affine predecessor and packed candidate also
matched every deterministic native solver counter on those 512 targets.

The executed source was committed as `74356ebc818495f82c793e1ec2817a16c3e42745`
before building, validation, and timing. The [build receipt](evidence/build-receipt.json),
[512-target semantic replay](evidence/semantic.json), and
[paired raw report](evidence/paired-report.json) retain source and binary
hashes, exact answers, work counters, paired order, failures, and individual
times. Each satisfying result independently passed the original field S3
relation, static Boolean equations, packed dynamic equations, and curve replay.

| Target abscissa | Status | Median packed/affine complete-query ratio | Median packed/compact complete-query ratio |
| ---: | --- | ---: | ---: |
| 0 | satisfiable | 0.592 | 0.469 |
| 1 | satisfiable | 0.639 | 0.537 |
| 2 | unsatisfiable | 0.844 | 0.630 |
| 9 | unsatisfiable | 0.886 | 0.759 |
| 100 | unsatisfiable | 1.048 | 0.737 |
| 511 | unsatisfiable | 0.993 | 0.700 |

The geometric means of the six cell-median ratios are 0.816 against the
affine predecessor and 0.629 against the compact path. One warmup and six
balanced-order triples ran per target: all 126 executions completed and
matched the frozen independent answer. Individual paired ranges are in the
raw report; several cells vary widely under host contention. The full
per-target timer starts before selecting target coefficients and ends after
the native solve, original-equation checks, and point replay. Reusable setup
is separate. Across the 36 measured packed-path calls, median packed-buffer
fill, native call, and independent equation-check times were 0.0168, 0.1268,
and 0.0056 ms respectively. These component medians do not sum to a paired
complete-query median.

The local macOS ARM64 host was shared and heavily loaded. These are
exploratory diagnostics: `timing_eligible` is false and
`qualified_speedup` remains null until a matched complete-query replay earns
the repository's [isolated-host receipt](../../docs/ISOLATED_BENCHMARKS.md).
The result is opt-in and leaves default routing unchanged. The next kernel
target is the remaining native dynamic-factor construction and boundary
elimination; further Python packing work has diminishing headroom in this
30-variable query.
