# Q1472: one-target N83 branch-polarity screen

The frozen compact four-summand WDSat search measured first-branch polarity
on one new ordinary N83 public point. Plain phase 0 reached its \(2^{20}\)
left-branch cap in **10.61 solver user CPU seconds**. Five random masks of
the exact selector, pair-midpoint, and leaf IDs reached that same cap in
**91.73–107.28 seconds** each, 8.64–10.11 times the phase-0 CPU cost.
Phase 6 reached at least \(2^{18}\) branches before its 900-second wall cap.
All seven completed full-lock controls returned SAT models replayed against
the original and width-four XCNFs.

| Phase | Ordinary status | Left branches counted | Solver user CPU s | Ordinary run wall s |
| ---: | --- | ---: | ---: | ---: |
| 0 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 10.614 | 113.353 |
| 1 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 96.710 | 470.952 |
| 2 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 107.276 | 229.893 |
| 3 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 91.734 | 305.524 |
| 4 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 106.901 | 793.469 |
| 5 | `BRANCH_CAP_REACHED` | 1,048,576 exact | 93.169 | 545.395 |
| 6 | `WALL_CAP_SEARCH_STARTED` | at least 262,144 | 48.832 | 900.045 |

The seven ordinary attempts charge **at least 6,553,600 left branches**
(\(2^{22.644}\)), **555.234 solver child user CPU seconds**, and
**3,361.243 target-dependent wall seconds** to the same point. The wall sum
includes the recorded cofactor-preimage and balanced-S3 formula build times
and every completed ordinary attempt. Solver child CPU excludes those two
Python/Sage preparation stages. The host had no isolation receipt; the CPU
and wall figures are exploratory method diagnostics.

The exact curve is `EC1N83Ckb1h876c2921cb64`, with actual factor-base size
`B=30,977,592`, signed-Frobenius folded columns `K=186,612`, and
`isogeny: "none"`. Workload `2eb250a29072` fixes one previously unseen
public point, its uniform-nonzero-scalar generation law and seed, all four
cofactor preimages, and the warm-base target count of one. `Q1472` remains a
proposal with `candidate_id: null` and `run_id: null`; the stage code is
`PDP4sat`. The [protocol](protocol.json), [freeze](freeze.json),
[target record](target.json), [build receipt](build_receipt.json), and
[phase receipts](runs) retain the source, binary, input, and resource identities.

The predeclared schedule contained phases 0–8. After phase 6 used its full
900-second wall allowance for 48.83 seconds of solver CPU under severe host
contention, the run was stopped for infrastructure efficiency. Control phase
7 was interrupted before producing a receipt; ordinary phases 7 and 8 were
unattempted. The [termination record](termination.json) and
[charged-attempt ledger](drive_receipt.json) make this departure explicit.
The [checked-Sage validator](validate.py) passed target scalar replay, all
four exact preimages, byte-for-byte reconstruction of both XCNFs, seven
control SAT replays, and the seven ordinary status and accounting receipts.

The [analysis](analysis.json) retains the complete N83 decomposition work,
complete N131 one-target work, and comparable gap to \(2^{61}\) as `null`
because the ordinary searches are censored and no field-operation count has
been calibrated from solver branches. The separate Q1462 conditional N131
weight-seven full pair-index model is \(2^{86.1847}\) counted pair-add
attempts, 25.1847 bits above an abstract \(2^{61}\) pair-add reference;
its sampled base and work unit differ from this exact N83 weight-five SAT
screen. For the exact N131 weight-six base, the [uniform-query bound](../README.md)
leaves less than \(2^{33.36}\) abstract work units per query under a
zero-other-cost \(2^{61}\) cap and its stated uniform marginal.

The next tuning pass should count CNF/XOR propagation and field operations,
then screen the four combinations of the two target-preimage selector-bit
polarities under a control gate on an isolated host. A completed ordinary
relation, independent group replay, and rank-novelty measurement would turn
that stage result into a cost-per-useful-row estimate for the N131 ledger.
