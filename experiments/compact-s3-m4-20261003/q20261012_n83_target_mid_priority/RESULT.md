# Q1507: target-side leaf priority cuts usable first-pair work 1.75–1.78× but not full capped search work

On the frozen ordinary N83 selected and holdout points, placing the two
target-side leaf blocks before the first-pair leaf blocks exposed an
independently replayed **two-root, exact-base usable first pair** in 53,498
and 55,822 combined CNF/XOR calls. The Q1488 leaf-pair-first order used
95,480 and 97,804 calls for that same pair. The reduction is 0.836 and
0.809 bits at this first-pair stage. All four leaf-order/target cells
replayed to the same first pair; the new order did not make it target
dependent.

| Phase-2 ordinary point | Q1488 leaf-pair-first | Q1507 target-side leaves first | Q1507 four-leaf interleave | First-pair roots and exact base |
| --- | ---: | ---: | ---: | --- |
| Selected, workload `2eb250a29072` | 95,480 calls | **53,498 calls**, branch 26 | 95,480 calls, branch 39 | 2 roots; both leaves usable |
| Holdout, workload `394256b9f901` | 97,804 calls | **55,822 calls**, branch 26 | 97,804 calls, branch 39 | 2 roots; both leaves usable |

The paired screen also retained phase 4 (rootless; one leaf outside the
base) and phase 5 (two roots; both leaves outside the base). The target-side
midpoint-first priority reached the **1,048,576-branch cap** on both targets
in each of those three phases before any complete first pair was exposed.
Its last selected and holdout checkpoints used 648,096,330 and 481,483,988
combined CNF/XOR calls. These failures remain capped search rows.

Four phase-2 full-chain continuations were then run to the same branch cap:

| Ordinary point | Target-side leaves first, final CNF/XOR calls | Four-leaf interleave, final CNF/XOR calls | Distinct first pairs at cap |
| --- | ---: | ---: | ---: |
| Selected | **450,937,110** | **450,937,110** | 1 in each run |
| Holdout | **450,939,434** | **450,939,434** | 1 in each run |

All four continuations have status `BRANCH_CAP_SEARCH_STARTED` and no SAT
model at that cap. This matched result makes the phase-2 first-pair saving
a local search diagnostic: it does not reduce the counted full-chain work
or increase pair diversity on these points. The next change must alter
how the solver leaves a completed first pair or tests the complementary
second pair, rather than only moving static leaf priorities.

The curve is `EC1N83Ckb1h876c2921cb64`, with exact usable W≤5 base
`B=30,977,592`, signed-Frobenius columns `K=186,612`, and base-set digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The stage is `PDP4sat` with `isogeny: "none"`; the IC candidate and run IDs
are null because this is a solver-stage comparison. The source-bound binary
adds the two priority arrays to Q1488 WDSat and keeps first-pair capture
active through the existing branch cap. All eighteen first-pair attempts,
four continuations, input and binary hashes, combined counters, exact
S3 roots, factor-base projection and subgroup replay, wall and CPU times,
and **per-child peak RSS** are archived. Peak RSS in the phase-2 screen was
about 0.90–0.91 GB. Wall-time ratios are exploratory because the host lacks
an isolation receipt.

The complete N83 relation yield and degree-131 full-solve exponent remain
unset by these capped cells. No challenge dispatch follows from them.
The [protocol](protocol.json), [build](build_receipt.json),
[first-pair receipts](result.json), [full continuations](continuation_result.json),
[analysis](analysis.json), and [read-only validator](validate.py) preserve
the matched result. Recheck with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n83_target_mid_priority/validate.py
```
