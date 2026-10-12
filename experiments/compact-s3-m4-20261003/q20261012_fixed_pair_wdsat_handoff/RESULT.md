# Q1514: direct raw-leaf branching reaches the N83 cap without a relation

The exact Q1513 one-link S3 handoff can be converted to WDSat's width-four
CNF format while preserving all native XOR rows. The N83 converted system
has **43,646 variables, 125,796 CNF clauses, and 1,247 XOR rows**. The two
long raw-x clauses account for the 80 auxiliary variables. Both archived
satisfying controls extend to assignments that pass every converted row.

This retrospective stage proposal is `Q1514`, `PDP4sat`, with
`isogeny: "none"` and null candidate and run IDs. It uses the same N53 and
N83 exact curves, base records, complements, and input hashes as Q1513. The
N83 base has B=30,977,592, K=186,612, digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The [protocol](protocol.json), [preparation receipt](prepare_receipt.json),
and [build receipt](build_direct_receipt.json) pin the XCNF transform and the
WDSat binary. The direct variant changes the Q1472 binary's branch priority
to interleave the two raw-x leaf vectors, IDs 2–84 and 18174–18256. All
other variable IDs follow in ascending order.

| Input and order | Outcome | Branches reached | Solver wall, exploratory | Child peak RSS |
| --- | --- | ---: | ---: | ---: |
| N53 known pair, inherited middle order | BRANCH_CAP_SEARCH_STARTED | 1,048,576 | 4.714 s | 112,672,768 B |
| N53 known pair, inherited leaf order | SAT_VERIFIED | 8,192 checkpoint before model | 0.074 s | 112,918,528 B |
| N83 pinned raw masks 3 and 9, inherited middle order | WALL_TIMEOUT_SEARCH_STARTED | at least 524,288 | 20.030 s | 895,041,536 B |
| N83 pinned raw masks 3 and 9, inherited leaf order | WALL_TIMEOUT_SEARCH_STARTED | at least 524,288 | 20.015 s | 635,305,984 B |
| N83 pinned raw masks 3 and 9, inherited interleaved order | WALL_TIMEOUT_SEARCH_STARTED | at least 524,288 | 20.018 s | 692,273,152 B |
| N83 pinned raw masks 3 and 9, direct raw-leaf order | WALL_TIMEOUT_SEARCH_STARTED | at least 524,288 | 20.016 s | 895,188,992 B |
| N83 selected ordinary, direct raw-leaf order | BRANCH_CAP_SEARCH_STARTED | 1,048,576 | 16.943 s | 605,716,480 B |
| N83 holdout ordinary, direct raw-leaf order | BRANCH_CAP_SEARCH_STARTED | 1,048,576 | 15.592 s | 605,716,480 B |

The inherited leaf order's N53 SAT model passes both the original and
converted XCNF and independent curve replay. The N83 pinned controls are
known satisfiable from Q1513's independently checked CryptoMiniSat model;
their WDSat wall caps measure a censored search, not unsatisfiability.
Both ordinary N83 direct-order runs searched and reached their branch cap
without a model. No verified ordinary relation or rank row was produced in
these runs. Host isolation was not recorded, so wall ratios are exploratory.

The direct order does not yet improve the solver gate: even a pinned N83
control is unresolved at the cap, while Q1513's CryptoMiniSat control is
verified. Cost per useful ordinary relation and the fully charged N131
single-target work exponent remain unset. The immediate next experiment is
to reduce N83's cofactor-projection leaf circuit or provide a stronger
root-aware inference rule, then require the pinned N83 control and an
ordinary relation before projecting N131 cost.

Validate the exact transform, source patch, binary, inputs, raw outputs,
statuses, and model replay with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_fixed_pair_wdsat_handoff/validate.py
```
