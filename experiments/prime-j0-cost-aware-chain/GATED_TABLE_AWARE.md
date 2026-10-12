# Demand-gated second Eisenstein recode: prospective experiment

The two-representative hot-orbit selector in PR #275 saves additions but
recodes two complete atlas streams for nearly every nonzero scalar. This
candidate performs the second recode only when the first stream has a cold
two-digit eight-step block or exceeds the prepared span. A cold block has
both four-digit halves nonzero and its six-unit orbit absent from the
2,048-entry hot table. One-digit and zero blocks alone do not trigger the
second recode. If triggered, the second candidate is selected only when it
fits the table span and predicts strictly fewer mixed additions. L1 and
enumeration ties retain the baseline, exactly as in PR #275.

Both arms use the same point table, positional fallback, and 128-output
normalization. The gated arm counts actual second recodes in its benchmark
output and charges all scalar-dependent selector work to its online timer.
The branch behavior makes this suitable only for public research scalars.
The table remains target-dependent setup when the base point depends on
the target in a one-target rho solve.

## Prospective evaluation

Protocol commit and draft PR must precede new candidate inputs. Four
fresh 4,096-scalar curve/point workloads will use exact uniform rejection
sampling from SplitMix64 initial state
`20270217 ^ (curve_index << 32) ^ point_index`. The cases are the two
registered subgroups, generator and `37P`, with independent generic
output digests. Compare `fused-hot-batch128`,
`fused-hot-adapt2-batch128`, and
`fused-hot-gated-batch128` on each identical file, rotating arm order.
Preserve raw failures and the complete operation and selector counters.

The prospective gate requires all 16,384 gated outputs to match generic
multiplication; at least 3% fewer executed mixed additions than ordinary
hot in every case; at least 75% of the always-two selector's addition
saving retained in every case; and actual second recodes no more than 75%
of nonzero scalars in every case. Preparation operations and bytes must
match across the three arms. These are operation gates, not a wall-time
speedup claim. The isolated-host service must run five paired AB/BA
repetitions before any CPU speed or rho impact conclusion.

A separate 5,000-scalar-per-law feasibility screen from seed base
`20270201` saw 84.03%–99.70% of addition savings retained while
performing second recodes for 20.54%–65.98% of scalars. These numbers
helped freeze the gate and are exploratory, not candidate evaluation
evidence. `gated-table-aware-screen.json` records all four law rows and
source hashes. Academic novelty is not established.

## Executed frozen panel

Protocol commit `68b7d231` and draft PR #277 preceded the fresh scalar files.
`check_gated_panel.py` ran all three arms on each file, replayed every
output against generic multiplication, and independently predicted both
executed additions and actual second-recode counts. All 16,384 gated
outputs and all four selector-count rows verify.

| Case | Ordinary hot adds | Always-two adds | Gated adds | Always-two saving retained | Gated second recodes |
| --- | ---: | ---: | ---: | ---: | ---: |
| 32-bit subgroup, generator | 9,201 | 8,664 | 8,764 | 81.38% | 840 / 4,096 |
| 32-bit subgroup, `37P` | 9,181 | 8,661 | 8,758 | 81.35% | 841 / 4,096 |
| 56-bit subgroup, generator | 23,576 | 21,933 | 21,935 | 99.88% | 2,698 / 4,096 |
| 56-bit subgroup, `37P` | 23,730 | 22,007 | 22,010 | 99.83% | 2,783 / 4,096 |

The gated arm saves 4.61%–7.25% of ordinary-hot mixed additions and
meets every prospective operation and recode gate. All three arms have
identical preparation additions, 8,192 or 12,288 per point, and identical
prepared bytes, 300,144 or 431,216. `gated-panel.json` retains raw stdout,
failures, input and source hashes, selector counter checks, and all phase
operations. The local `test_curve` passed 409,269 checks.

The raw wall intervals in that receipt are exploratory because this host
is contended. The smaller subgroup's gated interval happened to be near
the ordinary-hot interval; the larger subgroup's remained above it.
Neither observation authorizes a speedup or slowdown claim. The two
isolated AB/BA comparisons, gated against ordinary hot and gated against
always-two, remain unrun.
