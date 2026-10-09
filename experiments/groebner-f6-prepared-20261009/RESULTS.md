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
exhaustive enumeration and six selected S3 targets. All 30 measured cold and
prepared pairs matched in peak factor words, witness words, eliminated
variables, membership tests, and transform XORs as well as answer and state
counts.

The frozen source commit is `31b5bb755a0a9f50305ab9b16c9f5a15c6e33316`.
The raw replay is [evidence/semantic.json](evidence/semantic.json) (SHA-256
`35b0f0b05d07c1fd74f6eaad4c74b1ada012442206eb3f3340aeceb929a1ed0e`)
and the raw paired panel is [evidence/profile.json](evidence/profile.json)
(SHA-256
`2febdf9cf10f2d2f4ddc38d4aed54429c06123334cda3642a8e8544375a7647e`).
The build receipt in the raw panel identifies both compiled libraries,
compiler, architecture, and source digests. Both arms used the same 21-variable
bag limit, 100-million-state logical cap, target law, and independent checks.

The layout holds 296,948 64-bit factor words (2,375,584 bytes). Its setup took
190.407 ms including Python fixture and native layout construction; native
layout setup alone took 107.326 ms. It precomputed 19,004,432 factor states
and 199,101,968 ANF-transform XORs. Those operations remain in the logical
per-query cap and counters, but their physical work is reused after setup.
Fresh queries had a median 19,019,664 total logical factor states and
4,265,472 elimination states. The median measured native prepared phases
were 0.042 ms for cached-factor copying, 0.052 ms for target-specific factor
construction, and 144.546 ms for elimination. This identifies elimination
as the next kernel target after factor preparation.

The local macOS panel used one warmup and five measured alternating AB/BA
pairs per target. Its timer starts before target-specific equation construction
and ends after ANF and curve-point replay; setup and source loading are
recorded separately. The table gives exploratory complete Boolean-query
diagnostics from this contended host. Ratios are the median of the five
paired `prepared/cold` wall ratios, not the ratio of medians.

| Target x | Status | Cold median ms | Prepared median ms | Median pair ratio | Pair-ratio range |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | satisfiable | 196.074 | 132.413 | 0.785 | 0.273–2.116 |
| 1 | satisfiable | 179.862 | 134.199 | 0.658 | 0.404–1.396 |
| 2 | unsatisfiable | 335.498 | 213.231 | 0.576 | 0.272–1.123 |
| 9 | unsatisfiable | 346.733 | 201.314 | 0.567 | 0.122–2.347 |
| 100 | unsatisfiable | 305.601 | 191.603 | 0.623 | 0.432–1.199 |
| 511 | unsatisfiable | 286.224 | 98.886 | 0.611 | 0.113–0.681 |

The required next measurement is the same frozen complete-query panel on a
physical isolated Linux CPU with the host receipt specified in
`docs/ISOLATED_BENCHMARKS.md`. The current host cannot supply that receipt.
After that gate, the next engineering experiment is to precompute an
elimination schedule or compress repeated static factors while preserving the
exact target-specific search and independent checks. A subsequent one-target
IC comparison will pair relation yield, rank, descent, and scalar recovery
against rho under the repository's complete-pipeline measurement contract.
