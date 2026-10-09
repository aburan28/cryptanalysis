# Reusable packed factors preserve every frozen S3 query answer

An immutable layout of target-independent Boolean factor tables was built once
for the `GF(2^9)`, four-summand, three-bit-subspace S3 chain. Fresh target
queries still build their final nine S3 equations and factors, eliminate every
variable, check the original ANF, and replay positive assignments with curve
points. The prepared and cold implementations matched on all 512 target
abscissae: two satisfiable targets (`0`, `1`) and 510 unsatisfiable targets.
Every status, assignment, point check, width, logical factor-state count, and
elimination-state count matched the independently enumerated predecessor
screen. The optimized and UBSan binaries also passed 90 random systems against
exhaustive enumeration and six selected S3 targets.

The frozen source commit is `3086da1b5ca545decb854f1e8a8abbffcd2d2960`.
The raw replay is [evidence/semantic.json](evidence/semantic.json) (SHA-256
`a9c08e601c4908a75c4c5bbca7b9f3b9000023de877f598a95abf1fe1192d9f6`)
and the raw paired panel is [evidence/profile.json](evidence/profile.json)
(SHA-256
`d00abfa67392b09634e4356c5f6ccaed76c5d0f5ced5d0d0ae972734319d56e5`).
The build receipt in the raw panel identifies both compiled libraries,
compiler, architecture, and source digests. Both arms used the same 21-variable
bag limit, 100-million-state logical cap, target law, and independent checks.

The layout holds 296,948 64-bit factor words (2,375,584 bytes). Its setup took
265.559 ms including Python fixture and native layout construction; native
layout setup alone took 199.918 ms. It precomputed 19,004,432 factor states
and 199,101,968 ANF-transform XORs. Those operations remain in the logical
per-query cap and counters, but their physical work is reused after setup.
Fresh queries had a median 19,019,664 total logical factor states and
4,265,472 elimination states. The median measured native prepared phases
were 0.042 ms for cached-factor copying, 0.050 ms for target-specific factor
construction, and 162.942 ms for elimination. This identifies elimination
as the next kernel target after factor preparation.

The local macOS panel used one warmup and five measured alternating AB/BA
pairs per target. Its timer starts before target-specific equation construction
and ends after ANF and curve-point replay; setup and source loading are
recorded separately. The table gives exploratory complete Boolean-query
diagnostics from this contended host. Ratios are the median of the five
paired `prepared/cold` wall ratios, not the ratio of medians.

| Target x | Status | Cold median ms | Prepared median ms | Median pair ratio | Pair-ratio range |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | satisfiable | 297.091 | 219.805 | 0.579 | 0.305–1.628 |
| 1 | satisfiable | 337.519 | 154.745 | 0.487 | 0.082–0.696 |
| 2 | unsatisfiable | 337.852 | 201.579 | 0.600 | 0.299–0.864 |
| 9 | unsatisfiable | 293.006 | 111.747 | 0.384 | 0.142–2.283 |
| 100 | unsatisfiable | 536.988 | 154.666 | 0.273 | 0.077–0.486 |
| 511 | unsatisfiable | 427.376 | 109.773 | 0.380 | 0.150–0.591 |

The required next measurement is the same frozen complete-query panel on a
physical isolated Linux CPU with the host receipt specified in
`docs/ISOLATED_BENCHMARKS.md`. The current host cannot supply that receipt.
After that gate, the next engineering experiment is to precompute an
elimination schedule or compress repeated static factors while preserving the
exact target-specific search and independent checks. A subsequent one-target
IC comparison will pair relation yield, rank, descent, and scalar recovery
against rho under the repository's complete-pipeline measurement contract.
