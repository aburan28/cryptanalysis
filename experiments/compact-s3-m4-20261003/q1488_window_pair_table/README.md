# Q1488: matched pair-table control on Q1481 window bases

The [pre-registered design](design_protocol.json) compares a bounded
signed-Frobenius pair table with Q1487 on the **same** N53/N83 curves,
exact Q1481 factor-base point sets, and Q1482 ordinary public points.
Q1445 demonstrated the pair-table method on Q1438's different weight
bases. Q1488 changes only the base and frozen workload needed for a direct
stage comparison; the pair-table setup is charged and reported separately.

N53 can materialize all 430,360 usable points from Q1481's 4,060 packed
projected x keys. N83 samples the full 348,006,384-point base from its
4,194,304 raw orbit representatives and verifies any sampled-point
certificate. The table/query caps are 500,000/1,500,000 pairs at N53 and
10,000/10,000 pairs at N83, with a 60-second target-dependent query cap.
The [protocol](protocol.json) freezes the inputs, limits, seeds, checked
Sage runtime, and exact stage IDs before the runs:

- `PS1N53Ckb1fb430360PDP4mitmh75f9a0c99d4f`
- `PS1N83Ckb1fb348006384PDP4mitmhea3f311d5fdb`

This remains proposal `Q1488` with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`. The stage code is `PDP4mitm`; its `fb430360` and
`fb348006384` counts are actual usable points before orbit folding.
A planted or synthetic collision is a correctness control. A verified
ordinary relation is a stage result, not natural relation yield, a
single-target DLP recovery, or a complete N131 `2^x`.

The [N53 materialization receipt](n53_window_points_receipt.json)
reconstructs 430,360 distinct subgroup points from Q1481's exact packed
keys and records the separate setup cost. The [pre-run control](validation.json)
checks the raw-orbit sampler mapping, a nontrivial quotient shift and
negative sign, 64 direct N83 sample certificates, subgroup membership,
and exact N83 key-set membership. No ordinary query has been run yet.
