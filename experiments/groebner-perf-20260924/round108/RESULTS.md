# Round108 results

Source freeze: `bd6ae687708f8b8b9b181d1c34f3474a45191034`. The first full validation attempt passed. The workload, arm order and budgets were frozen before execution. No numerical timing reruns were selected. This is a CPU-only diagnostic on an unisolated macOS ARM64 host; all qualified wall-time and IC speedups remain null.

The block method completes forward elimination on all five hard 12-variable controls: all 2,449 rows, rank 2,378. The scalar reference reaches only rows 2,190–2,254 before exhausting the same 20-million matrix-work cap. This is progress within the work budget, not a solved-query result. Three block cases exhaust the cap during parity proof rewriting. Two return candidate bases, but the independent checker rejects both because an original equation has a nonzero normal form. All five controls remain inconclusive after fallback, and their local full-query times increase.

Validation rebuilt 26 optimized/UBSan libraries from 104 recorded source files, with 12 generated files and two polynomial resources. All 11 test groups passed, including randomized exact graphs, every small work/node/row budget prefix, table-construction interruption, disabled mode, byte-cap boundaries, upper-triangular signatures, 64-bit boundaries, incomplete groups, ownership, concurrent fresh queries and forged-proof rejection.

The 78 correctness rows contain 38 independently verified algebra results (34 with curve replay), 40 inconclusive outcomes and no process failures. The 195 diagnostic rows include 39 warmups and 156 observations; 95 algebra results and 85 curve replays verify, 100 remain inconclusive, with no process failures. All 59 artifact corruptions and 21 synthetic publication corruptions are rejected. Synthetic publication controls are not remote CI receipts.

All 11 reference generated sources are byte-identical to round107, and all 52 shared F4/parity control records have identical deterministic traces. For all eight successful matrix fixtures, the scalar and block arms return identical exported proofs as well as identical bases.

## Exploratory query timings

Each cell is median ± median absolute deviation in milliseconds over four observations after one warmup. These intervals include target-dependent computation, certification, materialization and applicable equation/curve replay; target-independent setup and separate proof serialization/decoding are excluded. Inconclusive rows include the failed matrix attempt, checks and remaining-budget fallback. No ratio is promoted.

| Fixture | Scalar + parity, ms | Block4 + parity, ms | Both outcomes |
| --- | ---: | ---: | --- |
| pdp-6-seed-1 | 2.4482 ± 0.0640 | 2.5631 ± 0.1243 | solved |
| pdp-6-seed-3 | 3.2615 ± 0.0691 | 3.1723 ± 0.0869 | solved |
| planted-dense-mq-12 | 3.3972 ± 0.1750 | 2.7706 ± 0.0914 | gb |
| pdp-9-seed-1 | 8.9412 ± 0.2663 | 8.3381 ± 0.0252 | solved |
| pdp-9-seed-2 | 7.8514 ± 0.1861 | 7.1177 ± 0.1100 | solved |
| pdp-9-seed-3 | 8.5283 ± 0.0648 | 7.8652 ± 0.2408 | solved |
| pdp-9-seed-4 | 7.1797 ± 0.1180 | 6.2276 ± 0.1114 | solved |
| pdp-9-seed-5 | 9.3850 ± 0.0327 | 8.8748 ± 0.1744 | solved |
| pdp-12-seed-1 | 119.6823 ± 1.4232 | 123.8909 ± 1.4944 | inconclusive |
| pdp-12-seed-2 | 119.9687 ± 0.1806 | 125.4795 ± 1.0684 | inconclusive |
| pdp-12-seed-3 | 132.8885 ± 0.7778 | 144.0621 ± 6.6084 | inconclusive |
| pdp-12-seed-4 | 116.4899 ± 1.4349 | 126.4554 ± 0.3265 | inconclusive |
| pdp-12-seed-5 | 124.4269 ± 0.6064 | 130.3470 ± 0.2352 | inconclusive |

## Deterministic diagnostics

| Completed, verified fixture | Scalar matrix XOR words | Block XOR words, including construction | Scalar work | Block work |
| --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | 11,886 | 7,391 | 66,768 | 62,638 |
| pdp-6-seed-3 | 13,570 | 8,167 | 74,250 | 67,841 |
| planted-dense-mq-12 | 746,623 | 391,080 | 1,367,443 | 872,677 |
| pdp-9-seed-1 | 1,014,104 | 600,044 | 2,026,158 | 1,524,083 |
| pdp-9-seed-2 | 1,033,097 | 610,408 | 2,050,213 | 1,537,840 |
| pdp-9-seed-3 | 1,043,778 | 615,636 | 2,063,848 | 1,541,943 |
| pdp-9-seed-4 | 754,009 | 466,735 | 1,581,349 | 1,236,671 |
| pdp-9-seed-5 | 1,048,872 | 617,515 | 2,070,328 | 1,546,677 |

The largest table payload on the hard controls is 1,301,310 bytes, below the 4 MiB cap. This excludes vector headers, capacity slack and allocator overhead; process RSS and the producer row/proof/parity budgets have separate scopes. Work counts are declared software charges, not processor instructions.

## Next experiments

1. Reduce proof-processing work under the unchanged cap, especially compression performed before a candidate passes completion checks. Preserve the original witness and account for every attempted optimization.
2. Feed independently detected nonzero remainders into a bounded completion experiment, with original-input derivations. Compare against the existing F4 fallback at equal total producer/checker budgets. A wider multiplier degree by itself can greatly inflate the matrix and is not an assumed win.
3. Test a GPU tile implementation only after freezing the CPU block algorithm; include table creation, transfers, launch, synchronization and independent verification in one-query costs. Keep unmeasured GPU routing opt-in.
4. Obtain an auditable isolated CPU run before promoting timing ratios. A complete single-target IC/rho comparison remains a separate acceptance gate.

These changes do not establish a novel F6 algorithm, better Gröbner asymptotics, or world-fastest F4/F5. Fixed four-column tables are established linear-algebra engineering. See the prior-art links in README.md.

A supplementary native-free replay confirms nonzero remainders for all 31 input equations of each returned hard candidate (the first remainders contain 59 and 64 terms). It reconstructs candidates from the independent model; rejected native proofs were not exported. The first supplementary driver failed because it treated a result record as a list. Its script/log are retained beside the corrected passing replay; no native or timing runs were repeated.
