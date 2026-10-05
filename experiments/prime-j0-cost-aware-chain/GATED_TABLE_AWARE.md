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
