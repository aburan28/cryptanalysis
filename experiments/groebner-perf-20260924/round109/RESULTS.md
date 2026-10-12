# Seeded completion results

Two previously inconclusive hard 12-variable controls now complete within the
unchanged budgets. The final original-input derivations, ideal equality, Gröbner
completion, input equations and curve replay all verify. This is an untimed
Python reference experiment around the existing native producers. It establishes
additional completion within the work limits, not a CPU speedup or a native
integration result.

The matrix stage can return useful derived equations without returning a complete
basis. Instead of discarding those equations when the independent checker rejects
completion, this experiment supplies them first to F4, followed by every original
equation. It substitutes each seed's original-input derivation into the final F4
proof. A separate checker then verifies the composed proof against the original
packed coefficients. Every unsuccessful attempt and check consumes the shared
remaining budget. The Python bridge and proof composition have explicit charges.

The total producer budget remains 80 million declared work units; the matrix
sub-budget remains 20 million and the checker budget 200 million. The node cap is
2 million, the row cap 4,096 and the peak-live proof-term cap 2 million. Declared
work units are software charges, not CPU instructions or time measurements.

| Hard fixture | Round108 result | Seeded result | Total producer/bridge/composition work | Total checker work | Final proof nodes |
| --- | --- | --- | ---: | ---: | ---: |
| pdp-12-seed-1 | inconclusive | inconclusive | 80,000,000 | 0 | — |
| pdp-12-seed-2 | inconclusive | inconclusive | 79,999,404 | 0 | — |
| pdp-12-seed-3 | inconclusive | solved and replayed | 46,236,326 | 79,023,533 | 73,250 |
| pdp-12-seed-4 | inconclusive | solved and replayed | 41,603,558 | 79,445,824 | 73,397 |
| pdp-12-seed-5 | inconclusive | inconclusive | 79,999,966 | 0 | — |

The remaining three controls exhaust matrix proof processing before returning seed
rows. They retain the previous fresh-F4 fallback, which also exhausts its budget.
Their checker cost is zero because neither producer returns a candidate to check.
All eight previously successful fixtures retain the same basis, outcome and
producer/checker counts. These are small planted correctness controls, not natural
relation-yield estimates or complete IC variants.

## Validation and provenance

Initial discovery source: `8caafd6b1be1fe89ab5aa8d8bdec2353d33e3e08`.
Full validation source: `5c2aed25be6663b27577e45c303d03ed40580861`.
The validation revision adds retained continuation proofs, an independent audit
and portable locking. All 26 numerical/discrete discovery records are unchanged
after excluding the newly retained raw continuation artifact.

The fresh validation passed all four steps: build, discovery, independent audit
and artifact controls. It rebuilt 26 optimized/UBSan libraries from 104 recorded
sources. All 12 generated sources and both polynomial resources match round108.
Each of 13 fixtures ran in a fresh worker in both modes with a 60-second timeout.
The 26 rows contain 20 verified algebra results, 18 curve replays, six inconclusive
outcomes and no process failures. Optimized and UBSan results agree exactly.

Four unit-test groups cover 100 randomized nested-multiplication graphs, small
work/node budget prefixes, malformed unused nodes, input mapping, empty bases
and repeated outputs. The native-free audit replays proof polynomials with Python
integer bitsets, independently checks ideal equality/completion through the frozen
Boolean zero/staircase certificate, replays the curve and reconstructs the exact
composition and bridge ledger. It checks peak live terms while releasing proof
values after their last use.

All 10 coherent artifact corruptions and 16 synthetic publication corruptions are
rejected. Synthetic publication controls are not remote CI receipts. The evidence
archive retains both discovery and full validation, scripts, native build inputs
and binaries, raw outcomes, audits and negative-control summaries. No timing
panel was run, and all qualified speedups remain null.

## Next experiments

1. Move the seed handoff and proof substitution into a bounded native API. Keep
   original inputs, independent verification and the Python reference for exact
   comparison. Include composition, packing and fallback work in measurements.
2. Compress matrix witnesses before ordinary graph pruning. Test whether avoiding
   duplicate graph passes lets the other three hard fixtures return useful seeds
   within the same cap. Preserve strict size improvement and every failure path.
3. Measure complete query time on frozen inputs, with an auditable isolated CPU
   receipt before promoting ratios. Coverage gains alone do not establish speed.
4. Investigate GPU pivot tiles only with table construction, transfers, launches,
   synchronization and certification included in the single-query comparison.

This experiment supplies no new GPU result, proof of improved Gröbner asymptotics,
world-fastest F4/F5 claim or novel F6 algorithm. A complete independently verified
single-target IC/rho comparison remains a separate acceptance gate.
