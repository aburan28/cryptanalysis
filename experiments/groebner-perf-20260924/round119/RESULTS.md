# Bounded bitset normalization halves local native F4 time

The opt-in 4096-bit grevlex representation completed all five frozen hard
12-variable point-decomposition queries in optimized and UBSan builds (10/10).
The independent certificate, original equations, and curve checks passed.
Every paired query preserved the exact proof SHA-256, final reduced basis,
assignment, producer work, and checker work of the `round118` scratch-buffer
candidate. At 21, 32, and 64 variables, exact producer/checker controls passed
and each corrupted certificate was rejected. Wider-support calls use the
validated scratch-buffer path.

| Frozen query | Paired median complete-query bitset/scratch | Paired median native-F4 bitset/scratch | Complete-query ratio range |
| --- | ---: | ---: | ---: |
| `pdp-12-seed-1` | 0.857 | 0.542 | 0.554–1.077 |
| `pdp-12-seed-2` | 0.953 | 0.620 | 0.696–1.209 |
| `pdp-12-seed-3` | 0.679 | 0.491 | 0.642–0.834 |
| `pdp-12-seed-4` | 0.805 | 0.367 | 0.386–0.906 |
| `pdp-12-seed-5` | 0.840 | 0.571 | 0.734–0.948 |

The five cell medians have a geometric-mean ratio of 0.822 for the complete
query and 0.510 for native F4. One warmup and five alternating AB/BA pairs
ran per query, retaining all 60 executions. The complete-query interval begins
with fresh target coefficient descent and ends after independent proof,
equation, and curve checks and lease teardown. The field is `GF(2^31)` with
modulus `2147483657`; the binary curve has `b=1`. Each query has three
summands and four factor-base coordinates per summand. Target abscissae,
frozen equation digests, source hashes, raw intervals, and phase measurements
are in the evidence archive. The macOS M4 Pro host was contended, so these
wall-time ratios are exploratory diagnostics. A qualifying isolated-host
receipt is required before promoting a controlled CPU speedup.

The first three local panel attempts stopped before F4 because the new
worktree lacked `round108`, `round110`, and `round112` prerequisite builds.
Those reports and logs are retained as preflight records. After building the
prerequisites, the optimized and UBSan panel, larger-variable controls, and
paired profile passed. The frozen candidate source commit is
`c1e82f7d6ad2bfd317a9eb8bd1b7a9b11ceb96bf`.
The byte-verified [evidence archive](results.tar.gz) contains 292 logical
files and has SHA-256
`10d8ce0a1158766add8ba1ce6bdae74fa9bea4db5da94a326dbf64242973d82b`.

The next kernel test should reduce the cost of scanning all reducer terms in
`fits_bitset()` on each normalization call, preserving the 12-bit guard and
the same exact trace. Full-query CPU promotion remains gated on a matched
isolated host; the GPU crossover remains a separate physical-device gate.
