# Normal-reduction scratch results

The executable source is recorded in `summary.json` and the validation archive.
The retained build binds 59 sources, 18 rebuilt native libraries, two native
control executables, eleven generated sources and two regenerated polynomial
resources. Evidence/documentation commits leave the executed source closure
unchanged.

## Correctness

Five test groups pass with optimized and UBSan builds. Direct native controls
cover 6,144 combinations per build of polynomial terms, scratch caps, work and
proof-node limits. Additional controls cover high-bit masks, empty polynomials,
cancellation, operand aliasing, oversized release, counter saturation and
thread-local state. Python controls exercise complete fresh-target queries,
limit boundaries and concurrency.

All 184 correctness calls pass the native-free audit: 138 exact baseline/variant
trace pairs, 69 storage records reproducible across build modes, 80 certified
algebra outputs, 40 solved PDP calls and 104 unsuccessful calls. The single
preset diagnostic panel also passes: 552 calls (184 warmup, 368 observation),
414 exact trace pairs, 240 certified algebra outputs, 120 solved PDP calls and
312 unsuccessful calls. Seven distinct mathematical outputs are independently
rechecked. All 26 artifact corruption controls are rejected.

All four arms retain the same accepted bases, DAGs, producer and checker work,
failure reasons, solution assignments and independent equation/curve replay.
Every storage counter stays within its declared accounting rules. No native
or downloaded pickle artifact is executed by the independent artifact audit.

## Storage requests removed

The fresh-vector control has the same non-timing trace as the unchanged
baseline and exposes its merge requests. The candidate count below is
`fresh_vectors + growths`: explicit requests for new vector storage, not sampled
malloc calls, process RSS or a time ratio. Scratch reuse still performs the
complete symmetric-difference merge and proof emission.

| Fixture | Outcome | Fresh-control requests | Scratch requests | Reuses without growth | Peak retained scratch words |
| --- | --- | ---: | ---: | ---: | ---: |
| PDP 6, seed 1 | solved | 1,792 | 297 | 1,495 | 43 |
| PDP 6, seed 3 | solved | 781 | 126 | 655 | 48 |
| PDP 9, seed 1 | inconclusive | 4,023 | 878 | 3,145 | 318 |
| PDP 12, seed 1 | inconclusive | 2,844 | 681 | 2,163 | 2,086 |
| Dense MQ 16 | inconclusive | 4,791 | 442 | 4,349 | 568 |
| Random 8 | certified basis | 25,594 | 6,593 | 19,001 | 63 |

One mask word occupies eight bytes. The main arm caps retained scratch between
completed merges at 32,768 words (256 KiB). Actual peaks in this table are much
smaller. The tiny four-word arm exercises fallback and release: for PDP 6 seed 1
it records 1,722 fresh vectors, 59 growths, 11 reuses and 36 oversized releases.
Its transient peak is 16 words, but its retained peak is four. This distinction
captures the old input allocation immediately after swapping, before release.

## Complete-query timing does not establish a speedup

Milliseconds below are median ± median absolute deviation over four preset
observation calls. All successful PDP calls include fresh descent, native
solving/certification, materialized proof, extraction, original equation/curve
replay and lease teardown. Setup remains separate.

| Fixture | Baseline | Fresh control | Scratch | Tiny cap |
| --- | ---: | ---: | ---: | ---: |
| PDP 6, seed 1 | 4.247 ± 0.262 | 4.193 ± 0.147 | 4.195 ± 0.208 | 4.327 ± 0.103 |
| PDP 6, seed 3 | 3.857 ± 0.114 | 3.705 ± 0.164 | 3.677 ± 0.004 | 3.640 ± 0.095 |
| PDP 9, seed 1 | 18.406 ± 0.095 | 18.357 ± 0.276 | 18.411 ± 0.060 | 18.463 ± 0.146 |
| PDP 12, seed 1 | 55.399 ± 0.740 | 55.032 ± 0.704 | 55.749 ± 0.411 | 55.134 ± 0.338 |
| Random 8 | 25.968 ± 0.120 | 25.656 ± 0.344 | 25.104 ± 0.255 | 27.053 ± 0.292 |

The host has no qualifying isolation receipt. Qualified, aggregate and online
speedups remain null, with all raw timings preserved and no selected reruns.
These observations do not support a 2× complete-query claim or a new default.
The thirteen hard fixtures still stop at their identical producer work limit;
lower time to an inconclusive result would not establish a solved-query win.

## Next decision and scope

Retain the candidate as an explicit storage option. Fresh baseline stack
samples now identify repeated sorting in `ordered_multiple` on the twelve-variable
fixture. The image UUID and sampled addresses match the retained binary and
its introsort call-site disassembly. See [SAMPLES.md](SAMPLES.md) for the evidence
and the next bounded integer-order-key hypothesis. These samples are diagnostics,
not qualified timing measurements, and do not establish a universal bottleneck.

This remains a component experiment on frozen algebra and planted PDP controls.
The five six-variable fixture labels contain two distinct targets. There is no
ordinary relation-yield estimate, complete recovered DLP, paired rho result,
new GPU crossover or F6 asymptotic result. Complete IC and CPU speedup fields
remain unknown until their respective measurement contracts are satisfied.
