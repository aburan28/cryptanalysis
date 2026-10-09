# Cached separator message answers every frozen fresh S3 target

The final S3 link depends on 12 of the 30 Boolean variables in the frozen
`GF(2^9)`, four-summand, `ell=3`, `b=1` chain. The new layout eliminates the
other 18 variables once at width 21, retains a 17-word boundary factor set
and 33,264 witness words, then builds the final nine target-dependent equations
and eliminates a fresh boundary copy per query. Positive answers pass the
original ANF equations in both native code and independent Python, followed
by curve-point replay. It matched the independently enumerated predecessor
screen on all 512 target abscissae: two satisfiable and 510 unsatisfiable.
Optimized and UBSan builds also passed 90 random systems against exhaustive
enumeration and six selected S3 targets.

The frozen source commit is `9d5dcbb8f88dbb0c2cb54b32cb4c76daaa2082b5`.
The [raw semantic replay](evidence/semantic.json) has SHA-256
`e906219eb5444b05036c93012a8ffe728a62a08c9efbbea1580361ec8d920f5c`;
the [raw paired panel](evidence/profile.json) has SHA-256
`c8d668b3a5a3337048fc88090932dd1cecb8e19893b95c687477ec8554454ed8`.
Every paired result includes the exact target, status, assignment, ANF check,
point replay, source/build receipt, phase counters, and timing interval.

Static preparation constructed 19,004,432 factor states and eliminated
4,257,792 states. These remain charged to the logical per-query state cap,
with physical work reused. The prepared baseline's cached factors held
296,948 64-bit words; the message's residual factors hold 17 words and its
witness maps hold 33,264 words. In the local run, the combined Python context
and both comparison layouts took 1,714.438 ms to set up; native message layout
setup inside that interval took 587.790 ms. This setup is target-independent
and is reported separately from the online interval. The comparison harness
also constructs the prepared baseline layout; a message-only deployment can
omit that extra setup.

The local macOS panel used one warmup and five measured alternating pairs per
target. The timer begins before fresh target-equation construction and ends
after independent ANF and curve-point replay. Ratios are medians of paired
`message/prepared` wall times, not ratios of medians. These are exploratory
diagnostics from a contended host and await an isolated-host receipt before
they can be promoted as controlled CPU speedups.

| Target x | Status | Prepared median ms | Message median ms | Median pair ratio | Pair-ratio range |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | satisfiable | 244.513 | 0.487 | 0.00213 | 0.00158–0.00393 |
| 1 | satisfiable | 172.089 | 0.952 | 0.00474 | 0.00232–0.00831 |
| 2 | unsatisfiable | 252.848 | 0.241 | 0.00095 | 0.00042–0.00116 |
| 9 | unsatisfiable | 227.049 | 0.293 | 0.00244 | 0.00079–0.08165 |
| 100 | unsatisfiable | 278.694 | 0.294 | 0.00105 | 0.00076–0.00162 |
| 511 | unsatisfiable | 143.680 | 0.312 | 0.00220 | 0.00117–0.00639 |

The native message-query medians were 0.001 ms for residual copying,
0.044 ms for target-dependent factor construction, and 0.114 ms for query
elimination. The next implementation pass should remove trivial elimination
of the 18 already-projected variables and compare against a direct
group-state or meet-in-the-middle representation. The next empirical gate is
the same complete-query panel on an isolated physical Linux CPU, followed by
ordinary relation-yield, rank, descent, and one-target IC-versus-rho runs.
