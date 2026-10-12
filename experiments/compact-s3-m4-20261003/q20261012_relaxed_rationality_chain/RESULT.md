# Q1515: widening the balanced N83 S3 leaves to weight seven preserves size but remains capped

On the same frozen ordinary N83 selected and holdout public points, widening
the balanced raw-preimage S3 leaf bound from weight five to six or seven adds
at most **656 variables and 1,304 CNF clauses**. All six ten-second
CryptoMiniSat attempts returned `INDETERMINATE`; their raw stdout, stderr,
XCNF, source hashes, and limits are retained. A separate weight-seven
control with four raw leaves and the two pair-sum x coordinates pinned
produced a **verified group relation in 0.062 exploratory seconds**. The
four-leaf-only pinned control remained capped at ten solver seconds.

The exact curve is `EC1N83Ckb1h876c2921cb64`; the two workload IDs are
`2eb250a29072` and `394256b9f901`. The exact weight-five base has
B=30,977,592 usable points, K=186,612 signed-Frobenius columns, digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Weights six and seven are **Q-proposal base changes**: their actual usable
counts and set digests are not enumerated here. This stage uses `PDP4sat`,
`isogeny: "none"`, and null candidate and run IDs.

| Weight bound | Formula variables / CNF / XOR | Selected outcome, wall and conflicts | Holdout outcome, wall and conflicts |
| ---: | ---: | --- | --- |
| 5 | 65,221 / 189,928 / 1,245 | INDETERMINATE, 13.49 s, 56,001 | INDETERMINATE, 11.09 s, 61,270 |
| 6 | 65,549 / 190,580 / 1,245 | INDETERMINATE, 10.91 s, 56,706 | INDETERMINATE, 11.06 s, 56,001 |
| 7 | 65,877 / 191,232 / 1,245 | INDETERMINATE, 13.29 s, 56,002 | INDETERMINATE, 15.31 s, 56,002 |

These are exploratory wall times on an unisolated host. Conflict counts are
CryptoMiniSat work counters, not field-operation equivalents. Each cap
includes its failed attempt; no ordinary model, verified relation, or novel
rank row emerged. The planted control is a correctness check and does not
estimate natural yield. The weight-five pair-table's separate N83 prefix
also remained capped without a relation, but its pair actions cannot be
converted to SAT conflicts without calibration.

The alternative four-leaf projected-x chain tested first in this directory
shrunk from 122,074 variables and 354,766 CNF clauses to 93,854 variables
and 271,766 clauses when raw-x rationality was deferred to model replay.
Its pinned control still returned `INDETERMINATE` after 11.21 exploratory
solver seconds. The existing balanced raw-preimage chain is smaller at
65,221 variables for weight five, so the projected-x relaxation is not
the chosen full-chain encoding.

The work needed per **verified ordinary relation**, complete N83 solve, and
fully charged N131 single-target exponent remain unknown. Widening the leaf
bound alone did not pass the solver gate at these caps, and the N131
`2^61` challenge run is not admitted. The next experiment should use the
same selected/holdout points to test a root-aware Boolean inference or
decomposition method, charging all retries and independent relation/rank
checks; if it returns ordinary rows, enumerate the enlarged base before
giving it an `IC1` identity.

The [protocol](protocol.json), [freeze](freeze.json), and
[validator](validate.py) bind and check inputs, formulas, statuses, and the
verified planted model. Reproduce the validation with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_relaxed_rationality_chain/validate.py
```
