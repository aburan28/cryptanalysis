# Normal4 two-matrix Gaussian elimination is active at 80,000 conflicts

The frozen two-matrix normal4-counter run admitted an
8,262-by-13,084 Gaussian component and printed `108K` elimination calls on
selected component 1. Its five-matrix control printed the same `108K` calls
on component 1, plus `2039` on component 4. Both independently audited
searches stopped naturally at the 80,000-conflict budget with exit code 15
and `BOUNDED_UNKNOWN`; neither external wall nor RSS guard fired.

The source is public ordinary query zero on
`EC1N131Ckb1h136f03e58c98`, with `B=11,743,888` distinct
subgroup-usable factor-base points, four raw target lifts, and the exact
normal4-counter six-summand XCNF SHA-256
`21b4c7c292fd1441f127428927fb6cf6c51849e279d97e72adbbd95343048d79`.
Both cells used pinned CryptoMiniSat 5.14.7 binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
one thread, 9,000-by-14,000 matrix limits, `--autodisablegauss=0`,
`--maxconfl=80000`, and the [frozen envelope](PROTOCOL.md).

| Matrix limit | Terminal status | Wall s | Peak sampled RSS MiB | Samples | Restart rows | Final conflicts | Selected matrices | Printed elimination calls |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 2 | `BOUNDED_UNKNOWN` | 70.394 | 774.641 | 245 | 282 | 80,002 | `[2,2]` | component 1: `108K`; others zero |
| 5 | `BOUNDED_UNKNOWN` | 65.264 | 1,267.250 | 233 | 282 | 80,002 | `[5,5]` | component 1: `108K`; component 4: `2039`; others zero |

The paired two/five sampled-RSS ratio is **0.611277**, a 38.872% reduction
in this run. [Trace comparison](runs/R1/trace_compare.json) confirms that
all 282 printed restart rows were byte-identical across the pair, despite
the extra calls on component 4 in the five-matrix cell. This establishes
the same printed restart trajectory through 80,000 conflicts, not identical
internal execution. Both cells reached the fixed conflict budget, so their
70.394- and 65.264-second walls are separate exploratory measurements on a
host without a CPU-isolation receipt; they are not a controlled timing ratio.

The [independent audit](runs/R1/audit.json) rehashes the archived and raw
formula, receipt, solver and executable sources, checks the exact flags and
caps, and recomputes matrix, restart, activity, status, and raw-log hashes.
The [manifest](manifest.json) binds the protocol, code, preflight, analysis,
and complete R1 receipts and transcripts. `preflight_before_R1.json` was
saved after the protocol commit and before either solver cell.

The activity observation answers the practical question left by
the [two-repeat matrix-count gate](../ecc2k130-equalb-gauss-count-20261010/RESULT.md).
The first selected component printed zero calls while the second printed
`108K`. Under the observed ordering, `--maxnummatrices=1` would retain
component 0 and exclude component 1; a separate run must verify how that
ordering behaves when the limit changes. The next controlled solver
experiment should test
component-aware selection or ordering on this same XCNF and conflict budget,
then measure ordinary-query relation yield only after independent replay of
a SAT model. The held-out 16/256-query prefixes remain unopened. Relation
rank, final matrix cost, target descent, and same-point rho remain separate
pipeline measurements; `candidate_id` remains `null`.
