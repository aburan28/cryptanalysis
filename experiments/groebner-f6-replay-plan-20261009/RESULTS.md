# Exact cached-prefix point replay lowers complete-query cost

The replay plan precomputes factor-base lifts and finite two-point sums, then
extends each returned witness through fresh group additions. On the frozen
GF(2^9), curve `b=1`, ell-7 four- and five-summand cases, it agreed with the
original Cartesian-product point verifier on **2,052 deterministic controls**
and on every returned witness. The source-bound optimized and UBSan panel
passed **4,096 complete queries and 12,288 native branch queries**. Every
paired arm had identical native statuses and assignments, every SAT witness
passed the original ANF and S3 checks, and the independent old point replay
agreed again outside the timed interval. No target answer is cached.

The final source was commit `2b377f31d117cd2f6c1b96d570b0720c7ebb5757`.
Each geometry had 66 liftable abscissae, 4,356 ordered pair-table slots, and
17,017 stored finite pair states. Optimized pair-table preparation took
151.17 ms for four summands and 175.06 ms for five. That reusable setup is
recorded separately from every target-dependent query.

The optimized panel alternated arm order over three repetitions of all 512
target abscissae per geometry. It retained **6,144 timed complete queries and
18,432 native branches**, plus twelve warmup queries. The interval includes
fresh packed coefficients, every native cutset branch, original field/static
ANF checks, and curve replay. Journal writes and the separate old-verifier
audit occur after each timed call.

| Summands | Reference complete median | Planned complete median | Paired geometric mean reference/planned | 95% target-cluster bootstrap interval |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 5.029 ms | 4.428 ms | 1.080× | 1.062–1.100× |
| 5 | 13.267 ms | 10.181 ms | 1.182× | 1.141–1.226× |

The work reduction is concentrated on verified positive targets. Their
median point-replay intervals were 1.055 ms versus 0.387 ms for four
summands, and 6.112 ms versus 1.790 ms for five. On the five-summand
positive subset, the paired whole-query ratio was 1.393× across 762
repetition/target pairs. On negative targets both arms finish without point
replay and had paired ratios near parity (1.003× and 1.005× for four and
five summands). The table's ratios include all 254 positive and 258 negative
target abscissae in each repetition. These are local diagnostics on an
unisolated macOS ARM64 host; controlled CPU speedup remains unknown until a
qualifying isolated-host receipt exists.

The [compressed report](evidence/report.json.gz) has SHA-256
`19cfbaa26721bfdd90d7e810356365b88699e62a8343ffb4735d10e7726cd8b0`.
The [complete journal](evidence/journal.jsonl.gz) has SHA-256
`d3cce5f0d2168a3c587a2fde1a202496a4b9f348dc467db92896fb7a776bd00e`.
They retain source and binary hashes, predecessor comparator identity,
individual controls, all branch decisions, original-verifier audits, timing
phases, and setup costs. The next complete-query optimization target is the
native target-factor and elimination work that dominates negative queries;
the pair table leaves those native operations unchanged.
