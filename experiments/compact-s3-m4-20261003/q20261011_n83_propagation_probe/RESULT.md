# Q1474: N83 selector polarity reduces propagation work at a matched prefix

On the frozen ordinary N83 four-summand query, flipping target-preimage
selector 2140 reduced CNF `set_true` calls by **14.89%** and XOR `set_true`
calls by **18.58%** at the same 32,768-left-branch checkpoint. The other
single-selector flip also reduced both counters, while flipping both raised
them. All four phases reached the frozen checkpoint after entering search.
This selects the 2140 flip for a deeper matched-prefix run.

| Phase | Selector flips | CNF calls at 2^15 branches | XOR calls at 2^15 branches | CNF / phase 0 | XOR / phase 0 | Solver user CPU s, exploratory | Solver wall s, exploratory |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | none | 9,618,398 | 10,631,934 | 1.000 | 1.000 | 0.622 | 13.398 |
| 1 | 2140 | **8,186,264** | **8,656,663** | **0.851** | **0.814** | 0.563 | 12.774 |
| 2 | 2141 | 8,529,496 | 10,039,644 | 0.887 | 0.944 | 0.593 | 14.794 |
| 3 | 2140 and 2141 | 10,078,371 | 11,812,047 | 1.048 | 1.111 | 0.595 | 13.419 |

The exact instance is `EC1N83Ckb1h876c2921cb64`, with 30,977,592
usable factor-base points, 186,612 folded columns, workload
`2eb250a29072`, `PDP4sat`, and `isogeny: "none"`. Q1474 remains a stage
proposal with null candidate and run IDs. The [protocol](protocol.json) and
[freeze](freeze.json) bind the Q1473 instrumented binary, ordinary XCNF,
public target, four exact masks, control replay, sources, and limits. Q1473's
four-mask native-XOR satisfiable control had a replayed SAT model for every
mask on that exact binary. Q1474 changes neither the binary nor the formula.

Each checkpoint is a deterministic prefix-work measurement. The runner
terminated a phase after reading its complete `Q1473_WORK 32768` record;
therefore every phase has status `CHECKPOINT_TERMINATED`, with 32,768 as a
branch lower bound and exact CNF/XOR counts at that point. The four solver
attempts add **54.384 exploratory target-dependent wall seconds** and
**2.373 solver user CPU seconds** to the same public point. Together with
Q1472's seven ordinary attempts, the [analysis](analysis.json) records 11
attempts, 3,415.627 target-dependent exploratory wall seconds, and 557.607
solver child user CPU seconds. The wall figure includes Q1472's preimage and
formula construction and Q1474's four solver launches; it is an attempt
ledger on one point, not a completed one-target online interval. No
checkpoint produced a relation, so a completed decomposition cost and
natural relation yield remain unmeasured. The cumulative child peak RSS
reached 897,351,680 bytes (855.78 MiB); the receipt does not attribute that
peak to any one later phase.

The two propagation counters are distinct internal call units. Their
matched-prefix reductions do not convert to a field-operation solve
exponent or predict later branches. The complete N83 decomposition work,
N131 one-target work, and comparable gap to `2^61` remain null. The separate
Q1462 conditional N131 weight-seven full pair-index model remains
`2^86.1847` counted pair additions, 25.1847 bits above an abstract
`2^61` pair-addition reference under its sampled-base and optimistic-rank
assumptions. It has a different operation unit and base policy from Q1474.

The next experiment is a matched phase-0 versus phase-1 ordinary search to
at least `2^18` branches, retaining both propagation counters and charging
both attempts to this public point. If the 2140 advantage persists, run a
new unseen N83 point with the selected polarity and independently verify
any returned four-point relation and its rank contribution before fitting
degree-131 work.

Reproduce the source/input and per-phase receipt checks with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n83_propagation_probe/validate.py
```
