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

All 256 query outcomes, including absences and caps, will enter the rank
and cost audit. One table setup is charged separately. Process wall times
remain exploratory without a host isolation receipt. Any full-rank log
recovery will be independently checked by scalar replay and labeled a
small-N53 comparator result; it cannot establish a sub-`2^61` N131 solve.

Reproduce custody checks with:

```sh
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/build.py --check
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/make_panel.py --check
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/freeze_protocol.py --check
```

Run the frozen panel once with `run_batch.py`, then audit with the accepted
Sage launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/run_batch.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/audit.py --emit
```
