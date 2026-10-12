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
and exact N83 key-set membership.

## Frozen ordinary results

Commit `9d5cd120` froze the source, runtime, materialized N53 point set,
sample laws, seeds, limits, and stage IDs before either run. The
[archive audit](archive_audit.json) independently replayed the N53
collision, exact base membership, subgroup membership, four distinct
folded columns, and the frozen public target sum. It retained the N83
zero-hit sample-cap row.

| Cell | Table preparation | Target-dependent query | Result | Verified relations |
| --- | --- | --- | --- | ---: |
| N53 ordinary | 500,000 pair samples; 24.422 s | 184,366 pair samples; 14.230 s | four-point relation | 1 |
| N83 ordinary | 10,000 pair samples; 6.886 s | 10,000 pair samples; 7.343 s | sample cap, zero key hits | 0 |

The [N53 receipt](runs/n53_ordinary.json) counts 500,000 table-phase
and 368,736 query-phase public curve `add` calls. The N83
[receipt](runs/n83_ordinary.json) counts full-base sampling and point
construction separately; its two samplers drew 80,305 raw orbit
representatives to accept 40,000 usable points. These are API call counts,
not calibrated field-operation equivalents. Both runs overlapped the Q1484
N131 census and lack a CPU-isolation receipt, so wall times are exploratory.

This is the missing matched-base comparison for Q1487. The compact
inverse-`S3` search passed its pinned controls but censored at 60 seconds
on this exact N53 ordinary target; Q1488 found one relation with its
separately charged pair-table setup. The different algorithms and
precomputation policies do not yield a controlled speed ratio. One N53
success does not estimate population relation yield or cost per novel
matrix row, and the N83 zero-hit cap does not measure successful N83
cost. The N131 full pair table remains outside the affordable path; no
complete N131 `2^x` or challenge permission follows.

## Reproduce

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1488_window_pair_table/build_n53_base.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1488_window_pair_table/validate_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1488_window_pair_table/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1488_window_pair_table/audit.py --check
```
