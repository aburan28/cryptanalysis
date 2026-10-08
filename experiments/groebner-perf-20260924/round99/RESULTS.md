# Bounded radix results

Executable source: `a11dd7ad430d40294f718ff83fb420648925e8db`. The build binds 60 sources,
18 rebuilt native libraries, two native control executables, eleven generated
sources and two regenerated polynomial resources. Evidence/documentation
commits leave the executed source closure unchanged.

## Correctness

All seven test groups pass on optimized and UBSan builds. The direct native
controls compare 16,384 multiplication cases per build against the unchanged
source method, including work and proof-node boundaries. Another 1,728 sorting
cases cover duplicates, constants, cutoff/cap boundaries, masks through bit 63,
oversized scratch release, reuse, counter saturation and every pass count from
zero through eight. Public-API tests cover bit 56/57/63 behavior, a large radix
query followed by a changed target, and concurrent invocations.

The native-free artifact audit passes 184 controls: 138 exact trace pairs,
69 sorting records, 80 certified algebra outputs, 40 solved PDP calls and
104 unsuccessful calls. The one preset diagnostic panel passes 552 calls
(184 warmups, 368 observations), 414 exact trace pairs, 240 certified algebra
outputs, 120 solved PDP calls and 312 unsuccessful calls. Seven distinct
mathematical outputs are independently checked. All 31 corruption controls
are rejected. Every proof, work charge, failure, accepted basis, assignment
and independent equation/curve replay matches the original producer.

## Radix work and memory

For PDP 12 seed 1, all 2,844 sorts qualify under the 128-term cutoff and
32,768-word cap. They process 1,140,509 terms using exactly three byte passes
per call: 8,532 active passes, 14,220 skipped passes and 3,421,527 scattered
words. The odd pass count causes 1,140,509 copied-back words before decoding.
Scratch grows ten times and is reused 2,834 times; its peak is 993 words
(7,944 bytes), below the 256 KiB cap. Scratch does not survive the query.

The 256-word control uses radix for 286 of these sorts and falls back on
2,558 over-cap rows, with a 249-word peak. On PDP 9 seed 1, both caps choose
77 radix sorts out of 4,023 calls. No sorts in the solved six-variable cases
or the random-eight control reach the cutoff. There is no basis for routing
every workload through radix.

## CPU-only complete-query diagnostics

Milliseconds are median ± median absolute deviation over four frozen
observation calls. Successful PDP intervals include fresh descent, native
production/certification, materialized proof, extraction, independent equation
and curve replay, and lease teardown. Reusable preparation stays separate.

| Fixture | Outcome | Original sorter | Packed keys | Radix | 256-word cap |
| --- | --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | solved | 3.918 ± 0.069 | 4.339 ± 0.027 | 3.998 ± 0.052 | 4.334 ± 0.186 |
| pdp-6-seed-3 | solved | 4.045 ± 0.022 | 4.011 ± 0.361 | 5.177 ± 0.305 | 5.307 ± 0.539 |
| pdp-9-seed-1 | inconclusive | 20.107 ± 0.814 | 18.322 ± 0.221 | 18.911 ± 0.780 | 18.115 ± 0.149 |
| pdp-12-seed-1 | inconclusive | 54.916 ± 0.390 | 44.565 ± 0.545 | 40.908 ± 0.228 | 43.026 ± 0.506 |
| random-8-budget-control | gb | 26.329 ± 0.163 | 26.054 ± 0.189 | 26.840 ± 0.650 | 26.482 ± 0.616 |

The host lacks a qualifying isolation receipt. Qualified, aggregate and
online speedups remain null. All observations, including regressions and
inconclusive results, are retained; no selected rerun replaces them. Small
solved controls do not improve consistently. The twelve-variable reduction
is time to the same work-limited failure, not a verified solved-query gain.

## Next decision

Keep radix opt-in. A frozen higher-budget completion panel is the next useful
engineering gate: compare original sorting, packed keys and radix on the same
larger fixtures, preserve every failed attempt, and determine whether the
benefit persists through completed independent certification and replay.
Pair completed queries on an isolated CPU host before promoting a timing
claim or changing dispatch. Further pass fusion/copyback removal is a
separate unimplemented hypothesis, not an inferred additional speedup.

This remains a generic algebra/planted-PDP component experiment. The five
six-variable fixture labels contain two distinct targets. It supplies no
ordinary relation-yield estimate, recovered DLP, paired rho comparison, GPU
crossover or globally fastest F4/F5 result. Bounded linear sorting of fixed
64-bit keys does not establish a new asymptotic Gröbner algorithm or F6.
