# Q1473: warm-table N53 relation collection and matrix-rank gate

Q1473 is a secondary, ordinary-target measurement of the exact N53
`PDP4mitm` comparator. It reuses Q1468's complete cross-column pair table
for 256 fresh seeded public subgroup points, then combines verified rows
with Q1469's prior 128-target panel while holding out Q1469 target 1.
The holdout is a known-representable correctness control and is excluded
from precomputation. This is not a compact chained-`S3` solver measurement,
a primary one-target timing claim, or an N131 work projection.

The exact curve is `EC1N53Ckb1hf77aab617904`. The selected factor base has
2,756 actual usable subgroup points, 26 folded signed-Frobenius columns,
and enumerated-set SHA-256
`cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70`.
The stage remains proposal `Q1473`, with `candidate_id: null`,
`run_id: null`, and `isogeny: "none"`. The [protocol](protocol.json) fixes
source and binary hashes, checked Sage runtime, 256 public targets, run
order, caps, and the predeclared holdout. It was frozen before the primary
run. The [control result](control_result.json) reproduces Q1469's archived
one-absence and one-witness cells exactly, including operation counts.

## Result

The frozen [run receipt](runs/primary/receipt.json) completed all 256
ordinary queries: **24 found, 232 complete absences, zero censored**. The
observed natural relation yield is **9.375%**, with a model-based Wilson 95%
interval of **6.381%–13.570%** under the seeded uniform target law. The
[independent Sage audit](audit_result.json) replays every witness on the
curve, checks four distinct folded columns and coefficient transport,
reconstructs every target seed, and independently recomputes matrix rank.
The [deterministic replay verification](verification.json) reruns the
mathematics and custody checks. It excludes only three freshly sampled
audit-wall intervals from byte-for-byte comparison.

Of the 24 new relations, **14 added rank** to the 12 retained Q1469 rows.
The combined matrix reached **26/26 rank after new query 152**. Sage solved
all 26 canonical factor-base logarithms modulo the frozen prime subgroup
order; each log independently replays to its factor-base point. The
predeclared held-out Q1469 target 1 was excluded from every precomputation
row, then recovered as scalar **6,872,560,257,754** and independently
replayed to its public point. This is a correctness control selected for
known representability, not a natural target-yield estimate or a primary
one-target online timing result.

| Charged measured scope | Field mul | Field sqr | Field inv | Exploratory phase wall |
| --- | ---: | ---: | ---: | ---: |
| One Q1473 shared table | 18,279,700 | 3,789,500 | 2,650 | 4.277 s |
| All 256 new queries, including absences | 4,288,499,976 | 868,258,788 | 209,499 | 1,143.932 s |
| Native collection through rank 26: 127 prior Q1469 queries with their fresh tables, Q1473's table, and its first 152 queries | **7,010,486,808** | **1,430,692,806** | **567,369** | **2,026.384 s** |

The last row charges the actual archived cache policies, including failed
ordinary queries. It is a sum of measured native phase intervals from the
two panels, not a single uninterrupted execution. The new panel's mean
target-query cost is 178,687,499 multiplications per verified relation;
including the 104 post-rank queries, it is 306,321,427 multiplications per
new novel row. The full-rank prefix alone spends 2,543,256,452 query
multiplications for its 14 new novel rows. The small N53 matrix build/rank,
solve, and 26-base-log-plus-holdout replay audit intervals were 0.009,
0.201, and 0.027 seconds, respectively, on an unisolated host.

Process wall times are exploratory without a host isolation receipt.
Factor-base construction, independent relation checks, target-query/recovery
as one online interval, and a matched one-target rho solve are not all
charged, so even an N53 full IC timing claim would be premature. The N83
compact solver still has no successful unpinned ordinary decomposition. The
complete N131 `2^x` remains unknown. For this **explicit complete-table**
method, Q1469's exact N131 base already requires about `2^64.222` entries
before a query; Q1473 does not change that conditional setup barrier.

Reproduce custody checks with:

```sh
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/build.py --check
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/make_panel.py --check
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/freeze_protocol.py --check
```

The frozen run has completed. Verify its mathematical result with the
accepted Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/verify_result.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```
