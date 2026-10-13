# Q1530: N53 calibration and 84-cell N131 quotient-reuse frontier

The exact N53 pair-table runs are consistent with the declared
`B²/(2r)` matched-query law once a partial table is priced by its
**distinct quotient keys**. Repricing all 84 frozen N131 weight/table cells
with Q1529's base-pair reuse selects the full W≤7 table as the least-work
cell whose matrix proxy is below `2^61`. Its conditional stage work is
**2^85.190199 pair-addition attempts**, **24.190199 bits** above an
abstract `2^61` pair-addition reference.

## N53 exact-base calibration

Both rows use curve `EC1N53Ckb1hf77aab617904`, W≤3 actual usable
`B=24,062`, folded `K=227`, subgroup order `r=21,044,858,204,113`,
enumerated base SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`,
and `isogeny: "none"`. Q1457's full table uses a fixed generator setup
target and 30 million query pairs. Q1451's smaller random table uses the
ordinary public-point workload `74f2979b3e68` and 1.5 million query pairs.
Their frozen independent replays verify relations and rank.

| Frozen N53 schedule | Distinct key coverage | Query pairs | Predicted matched positions | Observed matched positions | Observed / predicted | Wilson 95% rate interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q1457 full table, generator setup | 1.0000 | 30,000,000 | 412.68 | 399 | 0.967 | 1.206–1.467 ×10^-5 |
| Q1451 random 2m table, ordinary point | 0.51954 | 1,500,000 | 10.72 | 11 | 1.026 | 0.409–1.313 ×10^-5 |

The conditional prediction is `query_pairs × B²/(2r) × distinct_key_coverage`.
Q1451 sampled `2,000,000 / 2,743,068 = 72.91%` of table *descriptors*
but covered only `1,418,520 / 2,730,335 = 51.95%` of the complete
table's distinct keys. Using descriptor fraction would overstate its
expected yield. Both predicted rates lie in their recorded Wilson
intervals. Q1457 returned 400 verified occurrences at 399 query positions
and completed rank 227; Q1451 returned 15 occurrences at 11 positions
and 11 novel rows. The calibration keeps their different targets and
table schedules separate; it is evidence for the model at N53, not a
cross-degree success-rate measurement.

## N131 conditional parameter sweep

For each weight bound W≤5, W≤6, W≤7, W≤8 and fraction `f=2^-j`,
`j=0,...,20`, Q1530 recomputes the frozen Q1526 model with
`T=f·131·K²`, `Q=K·2r/(B²f)` lifted queries, and Q1529's native reuse
charge `T+(263/262)Q`. The final relation-matrix proxy remains `4K²`
**modular events**, a separate unit. W≤5 and W≤6 counts are exact
enumerations; W≤7 and W≤8 counts are sampled projections. Uniform query
support, proportional partial-table coverage, and one novel rank row per
useful match are optimistic model assumptions.

| N131 base | Full-table pair additions, log₂ | Matrix proxy modular events, log₂ | Matrix proxy below 2^61? |
| --- | ---: | ---: | --- |
| W≤5 | 93.766087 | 42.345126 | yes |
| W≤6 | 89.361105 | 51.155090 | yes |
| **W≤7** | **85.190199** | **59.496905** | **yes** |
| W≤8 | 81.228945 | 67.426030 | no |

The full [84-cell result](analysis.json) records each tested table fraction,
both old and quotient-reuse cost exponents, and the separate matrix proxy.
Every matrix-eligible cell exceeds the pair-addition threshold. The
[Lean proof map](FORMALIZATION.md) checks the finite minimum and budget
inequalities with no axioms. This is a go/no-go result for the **conditional
pair-index family**: its best eligible stage model is 24.190199 bits above
`2^61` before factor-base preparation, target descent, replay, or a measured
final matrix solve is added. Its complete N131 solve exponent remains
unset; there is no challenge dispatch from this screen.

The next experiment must change useful relation yield per charged query
or the factor-base/matrix tradeoff by roughly **24 work bits**, rather
than retune Bloom parameters or shorten the same table prefix. A concrete
gate is a target-conditioned second-pair method on the frozen N53 and N83
ordinary points, scored by verified novel rows per table-plus-query
addition. Measure the same input law and base on both degrees, preserve
caps and zero-yield cells, and only then refit the N131 projection.

## Reproduction

The [protocol](protocol.json) froze source hashes and the 84-cell grid
before the calculator ran. Recheck with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1530_quotient_calibration/validate.py
cd experiments/compact-s3-m4-20261003/q20261012_q1530_quotient_calibration/lean && lean Calibration.lean
```

Q1457, Q1451, Q1526, and Q1529 archived validators also pass on the
source records used here. CPU wall-time claims are outside this finite
operation-count analysis.
