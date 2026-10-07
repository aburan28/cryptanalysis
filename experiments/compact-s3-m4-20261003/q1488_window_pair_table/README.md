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
All limits and seeds will be frozen before the runs.

This remains proposal `Q1488` with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`. The stage code is `PDP4mitm`; exact `PS1` IDs will
use the actual `fb430360` and `fb348006384` counts after source freeze.
A planted or synthetic collision is a correctness control. A verified
ordinary relation is a stage result, not natural relation yield, a
single-target DLP recovery, or a complete N131 `2^x`.
