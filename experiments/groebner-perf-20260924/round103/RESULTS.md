# Round103 diagnostic results

The owned-byte transport preserves the exact proof and numerical work while
removing per-node Python object construction from the packed-output query.
The benefit is API-dependent: consumers requiring Python lists still pay a
separate decode cost. No numerical source was changed from round102.

Source freeze: `05b188fe1620832a8b04dda195c2d0c9e7ac51fb` (70 bound sources;
16 freshly built optimized/UBSan libraries). Local ARM64 macOS validation is in
`owned-proof-validation-v2` inside the lossless [evidence archive](results.tar.gz);
[archive.json](archive.json) binds the compressed bytes. The first attempt
passed build/unit tests but stopped during controls with disk-full; its partial
files, logs and explicit interruption record are retained. The successful rerun
used the same frozen sources and full preset panel. Timing observations were
not selected or rerun after inspecting results.

## Complete-query diagnostic times

Milliseconds, median ± median absolute deviation, four observations per cell
following one warmup, with arm order rotated as frozen in panel.json. The host
lacks an auditable isolation receipt: qualified, aggregate and IC online
speedups are **null**. Inconclusive cells are not solution-time comparisons.
PDP controls include fresh coefficient descent, production, independent native
certification, basis/proof ownership, extraction, independent equation and curve
replay, and lease teardown. MQ controls end at the certified algebraic result.
Reusable setup and artifact serialization/storage are reported separately.
These are planted small-system controls, not the original 18-variable workload,
ordinary-query yield measurements or complete IC/rho comparisons.

| Case | F4/hash | F4/dense | Matrix/list | Matrix/packed | Additional packed-to-list decode |
| --- | ---: | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | 4.497 ± 0.104 | 3.946 ± 0.064 | 3.083 ± 0.129 | 2.969 ± 0.178 | 0.088 ± 0.002 |
| pdp-6-seed-3 | 4.214 ± 0.076 | 3.769 ± 0.084 | 3.590 ± 0.063 | 3.418 ± 0.069 | 0.115 ± 0.015 |
| planted-dense-mq-12 | inconclusive (0/4) | inconclusive (0/4) | 26.565 ± 0.253 | 9.593 ± 0.357 | 11.360 ± 0.075 |
| pdp-9-seed-1 | inconclusive (0/4) | inconclusive (0/4) | 27.075 ± 0.552 | 16.965 ± 0.340 | 7.448 ± 0.272 |
| pdp-9-seed-2 | inconclusive (0/4) | inconclusive (0/4) | 27.766 ± 0.379 | 16.989 ± 0.212 | 7.315 ± 0.150 |
| pdp-9-seed-3 | inconclusive (0/4) | inconclusive (0/4) | 28.430 ± 0.296 | 17.325 ± 0.325 | 7.185 ± 0.124 |
| pdp-9-seed-4 | 82.918 ± 0.356 | 61.293 ± 0.547 | 23.373 ± 0.212 | 13.316 ± 0.289 | 7.482 ± 0.372 |
| pdp-9-seed-5 | inconclusive (0/4) | inconclusive (0/4) | 27.369 ± 0.496 | 16.193 ± 0.236 | 7.401 ± 0.401 |
| pdp-12-seed-1 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | — |
| pdp-12-seed-2 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | — |
| pdp-12-seed-3 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | — |
| pdp-12-seed-4 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | — |
| pdp-12-seed-5 | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | inconclusive (0/4) | — |

All four observations of each matrix arm certify the five nine-variable PDP
controls and the MQ control. F4 certifies only nine-variable seed 4 under the
same producer budget; F4 is inconclusive on the MQ control. Every arm remains
inconclusive on all five twelve-variable PDP controls. Those outcomes and every
fallback remain in the evidence. This experiment improves output transport,
not solver coverage or asymptotic complexity.

## What moved

| Case / arm | Producer ms | Checker ms | Proof materialization ms | Proof nodes |
| --- | ---: | ---: | ---: | ---: |
| pdp-9-seed-4 / matrix-list | 4.351 ± 0.074 | 5.409 ± 0.078 | 10.207 ± 0.186 | 39,409 |
| pdp-9-seed-4 / matrix-packed | 4.475 ± 0.101 | 5.448 ± 0.037 | 0.107 ± 0.044 | 39,409 |
| planted-dense-mq-12 / matrix-list | 3.999 ± 0.112 | 5.077 ± 0.118 | 16.973 ± 0.257 | 68,845 |
| planted-dense-mq-12 / matrix-packed | 3.859 ± 0.205 | 4.974 ± 0.014 | 0.345 ± 0.032 | 68,845 |

The arithmetic sums of observed query and separately observed decode costs
have medians 20.937 ms (nine-variable seed 4) and 21.064 ms (MQ12). These sums
are diagnostics, not directly timed list-returning queries. They demonstrate why
packed-output times must not be described as unchanged-list-API performance.
Serialization, proof sizes and process peak RSS are retained per observation in
`owned-proof-summary-v1.json` and the raw records. Process RSS includes setup and
post-query artifact decoding.

## Correctness and evidence

Nine unit-test groups pass, covering native cleanup and ownership, changed
coefficients, exact reference proof equality, independent algebra, 64-bit masks,
empty inputs, equation limbs, both byte orders, malformed containers, failed
budgets, nested/concurrent calls and injected-copy exception recovery.

- 104 optimized/UBSan control cells: 44 algebra certificates, 40 solved PDP
  controls, 60 inconclusive outcomes, zero process failures; 52 exact trace
  pairs, 44 lifetime checks, 28 equal-basis comparisons, 20 retained fallbacks.
- 260 diagnostic cells (52 warmups + 208 observations): 110 algebra certificates,
  100 solved PDP controls, 150 inconclusive outcomes, zero process failures;
  130 exact trace pairs and 50 retained fallbacks.
- All 39 corrupted-artifact controls rejected, including forged proofs with
  recomputed file hashes, altered format/copy counts, omitted decoding cost,
  missing replay, changed budgets, and invented timing claims.
- Fifteen synthetic publication-admission corruptions rejected. These validate
  the auditor and are not actual remote CI receipts.

The native-free audit verifies exact decoded DAG equality against list output,
ideal equality, Boolean Gröbner completion, independent equations/curve replay,
proof lifetime/work accounting and all source/resource hashes. Binary decoding
alone does not certify mathematics. Linux/macOS CI must build and verify the
published source independently before merge; local tests do not replace CI.

The next transport experiment should keep packed proofs through the actual
consumer boundary and measure any required conversion there. Checker arithmetic
and F4 production remain separate substantial costs. Harder frozen problems,
isolated CPU replay and GPU single-query crossover work remain required before
broader performance claims.
