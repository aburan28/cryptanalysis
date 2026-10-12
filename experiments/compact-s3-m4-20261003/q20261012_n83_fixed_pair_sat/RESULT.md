# Q1503: fixed first pair isolates the N83 middle-link search

Appending 166 unit clauses for the exact-base-usable Q1497 phase-50 first
pair makes the chained-\(S_3\) WDSat formula capture that pair at branch
one on each ordinary N83 public point. The solver then reaches its frozen
1,048,576-branch cap for all three 208-flip leaf-polarity masks on both
points. At the cap, both 83-bit leaf pairs have complete coordinate
assignments in at least 1,048,555 of the 1,048,576 branch snapshots per
cell. The bounded search has therefore moved past assigning the four x
coordinates and is spending its work on the remaining algebraic link and
consistency constraints.

The exact curve is `EC1N83Ckb1h876c2921cb64`, with the projected
weight-at-most-five base of **B=30,977,592** subgroup points and
**K=186,612** signed Frobenius columns. The ordinary workload IDs are
`2eb250a29072` and `394256b9f901`. Q1503 is a `PDP4sat` stage proposal,
with null candidate/run IDs and `isogeny: "none"`.

| Frozen 208-flip mask | Selected CNF/XOR calls at cap | Holdout CNF/XOR calls at cap | Status, both points |
| ---: | ---: | ---: | --- |
| phase 49 | 751,239,832 | 751,242,156 | `BRANCH_CAP_SEARCH_STARTED` |
| phase 50 | 721,653,295 | 721,655,619 | `BRANCH_CAP_SEARCH_STARTED` |
| **phase 51** | **558,306,267** | **558,308,591** | `BRANCH_CAP_SEARCH_STARTED` |

Phase 51 uses **0.370 fewer bits of CNF/XOR calls** than phase 50 at the
same branch cap. This is a capped stage diagnostic: none of the six cells
completed a satisfying four-point model within the cap. Q1499's unfixed
selected phase-50 continuation used 721,644,871 calls at the same cap;
fixing the usable first pair changed that count by only 8,424 calls. The
forced pair is visible in each solver log, so the close count reflects
continued second-link work rather than a failure to apply the unit clauses.

The [protocol](protocol.json) fixes the two targets, first-pair variable
range 168–333, three Q1497 masks, branch order, binary, and caps. The
[freeze](freeze.json) binds both Q1497/Q1498 first-pair receipts and the
SHA-256 of each transformed XCNF. [Per-run receipts](runs), the
[result](result.json), and the [analysis](analysis.json) preserve statuses,
CNF/XOR checkpoints, complete-leaf counters, CPU/wall diagnostics, and
source/input hashes. Wall values are exploratory on this unisolated host.

The next solver experiment should propagate the middle-link root domains
from the fixed pair into the remaining two-leaf problem before branching.
The exact Q1502 complementary-pair scan is the correctness reference for
that handoff. Degree-131 complete-solve work remains null until ordinary
relation yield, rank novelty, final matrix work, and target handling are
measured in one charged pipeline.

Recheck the preserved rows with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n83_fixed_pair_sat/analyze.py
```
