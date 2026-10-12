# Q1466: one-million-branch ordinary four-point WDSat measurements

Plain width-four WDSat completed **1,048,576 counted left-branch attempts**
on each of the exact N53 and N83 ordinary public points. This extends the
Q1464 fixed-branch screen by a factor of 64 under the same curve,
factor-base, workload, original XCNF, and shared-prefix encoding. Both
searches entered the solver and ended at the frozen branch cap with status
`BRANCH_CAP_REACHED`; the observed verified-relation count in these capped
attempts is zero. Both full-lock controls returned models replayed against
the transformed and original XCNFs.

| Field | Curve ID | Actual base B | Folded K | Branches | User CPU, s | Wall, s | Peak child RSS, MiB | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| N53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | 1,048,576 | 44.43 | 79.21 | 220 | `BRANCH_CAP_REACHED` |
| N83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | 1,048,576 | 67.50 | 248.25 | 858 | `BRANCH_CAP_REACHED` |

The N83 total user CPU at this fixed branch count was 1.52 times N53's.
The wall/CPU difference reflects the contended host, so neither wall time
nor this single CPU pair is a controlled speedup or a degree-scaling law.
Each run also had a 120-second CPU soft limit, 121-second hard limit, and
900-second wall limit. The branch cap was reached first in both ordinary
cells. `analysis.json` retains the exact CPU, system time, memory, input
identity, and receipt hashes; `validate.py` independently checks the
original and transformed formulas, binary, work markers, cap outcomes, and
control models.

The instrumented branch count covers WDSat's four `conf[0]++` left-branch
sites. It excludes Boolean propagation, Gaussian row operations, and field
operations. A capped search with no model does not estimate the work of a
completed point decomposition or natural relation yield. The full N131
single-target solve exponent and challenge gap remain null. The separate
Q1462 sampled W≤7 full pair-index model is still `2^86.1847` counted
pair-add attempts, 25.1847 bits above an abstract `2^61` pair-add
reference in that operation unit.

The next solver change is branch ordering on this frozen S3 system. The
current WDSat order processes one leaf's coordinate bits before moving to
the next. A controlled search can prioritize the target-preimage selector
or interleave the four leaf bit positions, then compare verified relation
output and total work against the same million-branch baseline. A returned
N83 model must be independently replayed as four rational points in the
exact factor base, then measured for relation rank novelty before it enters
the N131 ledger.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_deep_plain/validate.py
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_deep_plain/analyze.py
```

Q1466 is a `PDP4sat` stage proposal with `isogeny: "none"` and null
`candidate_id` and `run_id` pending a complete IC pipeline.
