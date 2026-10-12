# Q1484: both exact middle roots survive every matched N83 state

The Q1483 support checker was instrumented to count root compatibility
without changing its decisions. At the matched 32,768-left-branch
checkpoint on each of two frozen ordinary N83 points, **both** exact S3
middle roots remain compatible at all 32,720 recognized leaf-pair states.
There are zero singleton-root states and zero support rejections. The
combined CNF/XOR call counts match Q1483 exactly.

| Workload | Q1483 calls | Q1484 calls | Both roots compatible | One root compatible | Support rejections |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2eb250a29072` | 16,099,925 | 16,099,925 | 32,720 | 0 | 0 |
| `394256b9f901` | 16,102,249 | 16,102,249 | 32,720 | 0 | 0 |

The two roots agree on 49 of their 83 coordinate bits and differ on 34.
Their common bits are a potential implication while this exact leaf pair
is assigned; Q1484 does not count how many of those common bits are still
undefined. That count is the next gate before implementing propagation.

## Method and accounting

The curve is `EC1N83Ckb1h876c2921cb64`, with actual usable
normal-basis weight-five factor base `B=30,977,592`, signed-Frobenius
folded `K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1484 is a
point-decomposition stage proposal with null candidate and run IDs. The
[protocol](protocol.json) and [freeze](freeze.json) pin both public-point
workloads, the Q1483 binary source, exact roots, analysis code, phase-4
polarity, and resource caps. The [C patch](build.py) only counts zero,
one, and two compatible roots plus undefined bits in singleton states;
it does not change WDSat's branch or propagation choices.

Both ordinary attempts have status `CHECKPOINT_TERMINATED`. They add
12.065 exploratory solver wall seconds and 0.987 child user CPU seconds
to their respective point ledgers. Host isolation was not recorded, so
the wall and CPU times are diagnostics. [Validation](validate.py)
reconstructs the C patch, checks source, binary, input, run hashes,
replays Q1483's root validation, and verifies paired operation counters.

The frozen [analyzer](analyze.py) stopped at its post-run assertion
`0 <= minimum <= maximum <= 83`: with zero singleton observations,
the untouched counter sentinels are `(minimum=83, maximum=0)`. This is a
postprocessing assertion failure, not a solver failure. The original
analyzer remains frozen. [Corrected analysis](analyze_corrected.py)
accepts precisely that zero-count sentinel and records its own source
hash and the frozen analyzer hash in [analysis.json](analysis.json).
The two run receipts and raw solver logs were not modified.

## Challenge distance

No ordinary verified relation or rank contribution was produced by this
bounded prefix, so complete N131 one-target `2^x` work and the gap to
`2^61` remain null. The separate Q1462 conditional weight-seven
pair-index model remains `2^86.1847` counted pair additions, 25.1847
bits above an abstract `2^61` pair-addition cap in that distinct unit.
The next experiment should count undefined common-root bits at each
recognized pair, then test exact common-bit propagation if the count is
material.

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_singleton_support_probe/validate.py
```
