# Prepared constant witnesses: complete-query results

Fresh validation completed on 2026-10-04 from source
`3658ce3e36a4a7ae97f39a91c55cb768f9e3f34d`, on a physical Apple M4 Pro
(14 CPU cores, ARM64, 48 GiB, macOS 26.6, Python 3.13.1). The full checker
retains the original mode by default; prepared/folded modes are explicit.

| Validation | Result |
| --- | --- |
| Portable kernel controls, optimized and UBSan | 6,480 each; pass |
| Full checker API groups against unchanged round65 native checker | 9 pass |
| Fresh complete queries, 18 frozen inputs, 6–27 variables | 972 pass |
| Independent original-ANF proof/basis audit | All 972 records; 35 distinct proofs pass |
| Balanced complete-query diagnostic | All 324 fresh queries pass |
| Source/generated/native bindings | 595 checked |
| Archived binaries loaded by artifact auditor | None |

The panel crosses original/prepared/folded constant checking with the previous
producer/checker backend pairs, CPU sanitizers and serial/prepared/overlapping
preparation. Basis, proof, first assignment and logical producer/checker counts
match the original loop. Separate API controls retain exact rejection and
failure-prefix accounting, including altered and valid alternative witnesses,
budget failures, equation-width boundaries through 128, stale input, changed
configuration, cross-thread ownership and failed workspace allocation.

## Exploratory complete-query panel

The producer is Metal in every arm. The checker uses either CPU or fused Metal
for its coefficient transform, and one of the three constant-identity modes.
There are 18 observations per arm/case. The six-order Williams block balances
positions and all ordered predecessor pairs; it is repeated three times.
All per-query witness preparation, solving, independent certification,
original-equation checks, public-point replay, copies and synchronization are
charged. Reusable context, shader and scratch allocation is separately retained.
The 27-variable prepared/folded scratch has 1,048,576 bytes of witness elements.

| Frozen fixture | Transform / constant mode | Median query (ms) | Query IQR (ms) | Median constant check (ms) |
| --- | --- | ---: | ---: | ---: |
| n31-m3-ell6-seed101 | cpu / original | 0.965 | 0.923–0.992 | 0.043 |
| n31-m3-ell6-seed101 | cpu / prepared | 0.942 | 0.908–0.960 | 0.017 |
| n31-m3-ell6-seed101 | cpu / folded | 0.961 | 0.934–0.996 | 0.029 |
| n31-m3-ell6-seed101 | metal_simd / original | 1.058 | 1.015–1.132 | 0.044 |
| n31-m3-ell6-seed101 | metal_simd / prepared | 1.017 | 0.992–1.060 | 0.017 |
| n31-m3-ell6-seed101 | metal_simd / folded | 1.024 | 1.002–1.063 | 0.029 |
| n31-m3-ell8-seed201 | cpu / original | 13.703 | 13.520–14.340 | 1.252 |
| n31-m3-ell8-seed201 | cpu / prepared | 12.921 | 12.796–13.178 | 0.422 |
| n31-m3-ell8-seed201 | cpu / folded | 13.306 | 13.100–13.700 | 0.743 |
| n31-m3-ell8-seed201 | metal_simd / original | 12.223 | 12.106–12.605 | 1.265 |
| n31-m3-ell8-seed201 | metal_simd / prepared | 11.478 | 11.253–11.918 | 0.428 |
| n31-m3-ell8-seed201 | metal_simd / folded | 11.882 | 11.611–12.062 | 0.749 |
| n31-m3-ell9-seed201 | cpu / original | 116.152 | 115.450–117.854 | 6.371 |
| n31-m3-ell9-seed201 | cpu / prepared | 112.013 | 110.820–114.860 | 2.125 |
| n31-m3-ell9-seed201 | cpu / folded | 113.656 | 112.734–114.537 | 3.683 |
| n31-m3-ell9-seed201 | metal_simd / original | 109.396 | 107.779–110.059 | 6.389 |
| n31-m3-ell9-seed201 | metal_simd / prepared | 104.781 | 103.862–107.123 | 2.141 |
| n31-m3-ell9-seed201 | metal_simd / folded | 107.091 | 105.513–109.158 | 3.658 |

The constant-check column is nested within the query interval. Separate medians
must not be added together. IQR describes observation spread, not a controlled
effect. `paired-diagnostics.json.gz` also retains every within-trial difference
and a reproducible 10,000-resample paired percentile interval for both candidate
modes. Those intervals condition on this sample and do not model uncontrolled
host effects. One-minute host load ranged from 8.068 to 9.044.

The prepared mode is the stronger engineering candidate on these observations;
the folded expression remains a measured ablation. The largest fused-transform
query's median changes from 109.396 ms to 104.781 ms, while its nested constant
check changes from 6.389 ms to 2.141 ms. This is not another 2x query result.
There is no host-isolation receipt: controlled CPU speedup, aggregate speedup
and CPU/GPU crossover remain unknown. CPU transform and original identity mode
remain defaults. These controls are not natural relation-yield or IC/rho results.

## Evidence and next experiment

`query-results/` contains the frozen order, every query, setup costs, paired
diagnostics, checker/source/binary receipts, proof hashes, original-ANF audit,
logs and the complete local artifact index. Compact correctness metadata omits
only the raw proof payloads and cannot independently replay them. The full
bundle remains at the indexed local path and is regenerated/uploaded by the CI
workflow. Native libraries are rebuilt separately on each claimed platform.

The next larger engineering target is independent affine-multiplier checking,
followed by producer projection work. A GPU checker would need coefficients
reconstructed from original ANF, fresh proof uploads, bounded storage, exact
identity checks, honest accounting for work past any first failing record,
explicit capabilities and a CPU path. It must pass adversarial proof controls
and the original-ANF audit before a matched complete-query measurement. Removing
small transform copies alone is unlikely to produce another large query gain.
No asymptotic improvement or new F6 algorithm is established by this change.
