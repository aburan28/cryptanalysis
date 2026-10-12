# Q1475: selector 2140 keeps its N83 propagation advantage eight times deeper

On the same frozen ordinary N83 four-summand query, flipping target-preimage
selector 2140 used **14.95% fewer CNF** and **18.65% fewer XOR** `set_true`
calls than phase 0 at 262,144 left branches. This is eight times the Q1474
checkpoint; the relative reductions there were 14.89% and 18.58%. Both
phases entered search and reached the frozen checkpoint, so the prefix
advantage persists across these two depths on this public point.

| Phase | Selector 2140 | Left-branch checkpoint | CNF calls | XOR calls | Solver user CPU s, exploratory | Solver wall s, exploratory |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | unchanged | 262,144 | 76,940,413 | 85,081,823 | 3.144 | 84.263 |
| 1 | flipped | 262,144 | **65,437,262** | **69,215,920** | 2.678 | 73.102 |

The instance is `EC1N83Ckb1h876c2921cb64`, actual factor base
`B=30,977,592`, folded columns `K=186,612`, workload `2eb250a29072`,
stage `PDP4sat`, and `isogeny: "none"`. Q1475 has null candidate and run
IDs because it measures the decomposition stage. The [protocol](protocol.json)
froze phase 0 against the Q1474-selected 2140 flip before either deeper
attempt. The [freeze](freeze.json) binds the exact Q1474 runner source,
Q1473 instrumented binary and four-mask satisfiable control, original and
width-four XCNFs, target, code, and resource limits. The new wrapper uses
Q1474's `run_one` byte for byte; each phase retains its implementation
receipt and raw stdout/stderr alongside a Q1475 receipt.

The two attempts add **157.365 exploratory target-dependent wall seconds**
and **5.822 solver child user CPU seconds**. Across Q1472, Q1474, and Q1475
on the same public point, the [analysis](analysis.json) now charges 13
ordinary attempts, 3,572.992 exploratory target-dependent wall seconds,
and 563.429 solver child user CPU seconds. Q1472's target-preimage and
formula construction are included in that wall ledger. Cumulative child
peak RSS reached 898,236,416 bytes (856.625 MiB). The host had no
isolation receipt and load exceeded 300 during this screen, so wall and CPU
figures are descriptive; exact counter comparisons use the same branch
checkpoint and frozen inputs.

Both searches were terminated after their complete `Q1473_WORK 262144`
checkpoint. Their status is `CHECKPOINT_TERMINATED`, and neither yielded a
relation before that point. CNF and XOR calls remain separate internal
units; they are not a complete decomposition cost. The natural relation
yield, completed N83 decomposition work, normalized N131 one-target work,
and comparable gap to `2^61` remain null. The separate conditional N131
weight-seven pair-index model is `2^86.1847` counted pair additions,
25.1847 bits above an abstract `2^61` pair-addition reference under its
sampled-base and optimistic-rank assumptions. It is a different method and
operation unit.

The next gate is a matched phase-0/2140-flip check on one new unseen N83
point, then a deeper solver attempt using a mask selected without reference
to that point. Any returned relation requires independent four-point group
replay and rank measurement before a degree-131 work fit.

Validate source and input identities, retained implementation receipts,
raw work checkpoints, statuses, and phase accounting with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n83_polarity_depth/validate.py
```
