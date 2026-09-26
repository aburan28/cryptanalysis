# Compact-admissibility milestone results

One sequential run; timings are observations, not confidence intervals. All verdicts, point witnesses, orbit-coefficient rows, input pairing and source hashes validate.

| Milestone | Decision |
|---|---|
| Reliable n=13 decomposition decisions | Passed: both frozen phase patterns, including fresh holdouts. |
| Compact admissibility at table cost | Not passed: no payload enumeration, but compact/table CPU ratios are 1.516, 1.394. |
| Improving scaling | Not established: retain unresolved runs; no exponent fit or rho claim. |

## Frozen 100-target results

Each phase pattern uses the same 100 distinct sign-orbits. SAT counts are verified decompositions; UNSAT counts are correct negative decisions. Most targets have no decomposition in this small factor space.

| Phases | Variant | Decided | SAT | UNSAT | Timeout | Holdout decided | Max query wall (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| (0, 0, 0) | compact_s4 | 100/100 | 6 | 94 | 0 | 50/50 | 0.1462 |
| (0, 0, 0) | table_chain | 100/100 | 6 | 94 | 0 | 50/50 | 0.1479 |
| (0, 0, 0) | table_s4 | 100/100 | 6 | 94 | 0 | 50/50 | 0.0388 |
| (0, 1, 2) | compact_s4 | 100/100 | 19 | 81 | 0 | 50/50 | 0.1215 |
| (0, 1, 2) | table_chain | 94/100 | 19 | 75 | 6 | 48/50 | 1.0056 |
| (0, 1, 2) | table_s4 | 100/100 | 19 | 81 | 0 | 50/50 | 0.0483 |

Setup includes construction and both solver loads (including the holdout reset). All these costs are in total CPU. Rank is factor-base coefficient rank after folding sign/Frobenius.

| Phases | Variant | Setup + loads CPU (s) | Total CPU (s) | Rank | CPU / independent row (s) |
|---|---|---:|---:|---:|---:|
| (0, 0, 0) | compact_s4 | 0.0204 | 2.1207 | 4 | 0.5302 |
| (0, 0, 0) | table_chain | 0.0319 | 1.3172 | 4 | 0.3293 |
| (0, 0, 0) | table_s4 | 0.0403 | 1.3992 | 4 | 0.3498 |
| (0, 1, 2) | compact_s4 | 0.0234 | 2.0589 | 4 | 0.5147 |
| (0, 1, 2) | table_chain | 0.0330 | 10.2903 | 4 | 2.5726 |
| (0, 1, 2) | table_s4 | 0.0478 | 1.4771 | 4 | 0.3693 |

Across both patterns, compact total CPU is 4.1796 s versus 2.8762 s for table S4 (1.453 times the cost). Treat per-campaign ranks separately; summing them would double-count shared columns. The chain has unresolved targets in (0,1,2), so no equal-work speed ratio against it is reported.

## Four-size ladder

Twelve fresh targets per rung and variant, phases (0,1,2). All timeouts and correct negative decisions remain charged.

| n | l | Variant | Decided | SAT | Timeout | Rank | Total CPU (s) | CPU / independent row (s) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 7 | 4 | compact_s4 | 12/12 | 4 | 0 | 1 | 0.0257 | 0.0257 |
| 7 | 4 | table_s4 | 12/12 | 4 | 0 | 1 | 0.0084 | 0.0084 |
| 9 | 5 | compact_s4 | 12/12 | 1 | 0 | 1 | 0.0472 | 0.0472 |
| 9 | 5 | table_s4 | 12/12 | 1 | 0 | 1 | 0.0312 | 0.0312 |
| 13 | 6 | compact_s4 | 12/12 | 2 | 0 | 2 | 0.4106 | 0.2053 |
| 13 | 6 | table_s4 | 12/12 | 2 | 0 | 2 | 0.2485 | 0.1243 |
| 19 | 8 | compact_s4 | 0/12 | 0 | 12 | 0 | 12.6428 | undefined |
| 19 | 8 | table_s4 | 0/12 | 0 | 12 | 0 | 12.8078 | undefined |

The table domains contain 1, 1, 4 and 27 admissible source payloads, respectively. This very small and uneven factor space is a material limitation. Both n=19 runs return zero independent rows; their cost per independent row is undefined, not zero and not an extrapolated runtime. These censored observations do not demonstrate improving scaling.

## Next gate

Keep the compact implementation experimental. The next useful target is to preserve 100/100 decisions while reducing charged compact S4 CPU to at most the matched explicit-domain S4 cost in both n=13 phase patterns, then validate on a newly frozen holdout. The current run localizes the remaining cost to SAT search: compact setup is cheaper, but the larger inverse circuit costs more to solve. Do not count a smaller representation as a faster decomposition or retune on this already-observed holdout.

A Gröbner/F4 replay, robust measurements across larger completed rungs, final linear algebra, and a full equal-work comparison with folded rho remain unmeasured.

Environment: Python 3.12.14, pycryptosat 5.16.0, Linux-6.18.44-x86_64-with-glibc2.39. See [COMPACT.md](../COMPACT.md) for the proof, protocol and exclusions, and [compact_milestones.json](compact_milestones.json) for every observation.
