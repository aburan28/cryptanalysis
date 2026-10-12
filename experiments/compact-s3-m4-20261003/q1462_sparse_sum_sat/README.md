# Q1462: exact sparse-sum pruning in the target-linked SAT solver

Q1462 adds Q1461's exact fixed-midpoint pair inversion to Q1446's
target-linked, mids-first chained-`S3` SAT search. It checks partially
assigned leaf pairs when the number of possible XOR sums is at most 100,000,
even if the product of the two leaf option counts is larger than Q1458's
4,096-pair cap. A zero-pair result emits a clause guarded by that fixed
midpoint and the assigned leaf bits. Midpoint zero falls through to Q1446's
complete-pair and reverse-pair rules. A returned pair is only an x-coordinate
feasibility result; independent curve/subgroup relation replay remains the
acceptance gate.

The [protocol](protocol.json) and implementation were committed before the
ordinary runs. Both cells use the exact Q1438 public points, CNFs, curve
records, base digests, and resource limits also used by Q1446. N53 is
`EC1N53Ckb1hf77aab617904`, W≤4, with `B=324,042` actual usable base
points and `K=3,057` folded columns. N83 is
`EC1N83Ckb1h876c2921cb64`, W≤6, with `B=408,131,750` and `K=2,458,625`.
The Q1438 workload IDs are `6dfaff711b08` and `9ce3dd487274`.
Q1462 remains a `Q` proposal with `candidate_id: null`, `run_id: null`,
`isogeny: "none"`, and stage code `PDP4hybrid`.

## Correctness controls

The [pre-run control result](control_result.json) independently replays a
four-point relation at both degrees. Those planted SAT formulas propagate
their leaves before the new partial-pair rule runs, so they certify the full
solver path but have zero sparse-sum checks. Separate direct guard controls
force the new rule on Q1461's known satisfying and zero-pair states: at each
degree the rule retains one planted pair, rejects the zero-pair state, and
produces a guard false on the assigned state. Q1461's frozen probe separately
compared both states with direct pair enumeration.

The [archive verification](verification.json) checks receipt and input hashes,
and independently enumerates the complete pair domain for 24 recorded
Q1462 rejection snapshots at each degree. All 48 agree with the reported
zero-pair predicate. This covers the retained snapshots, not every one of
the thousands of checks.

## Ordinary result

Both ordinary cells reached the 60-second native cap and recovered no
relation. The counts include failed search work. Wall times are exploratory:
the host has no CPU isolation receipt, and the methods traverse different
prefixes within the same cap.

| Degree | Exact sum checks / rejections | Sum candidates visited | First recorded direct pair domain | Verified relations | Charged PDP stage wall | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 2,070 / 2,070 | 51,528,073 | 67,677 pairs | 0 | 61.979 s | 40,337,408 bytes |
| N83 | 1,357 / 1,357 | 46,396,800 | 249,719 pairs | 0 | 67.855 s | 80,609,280 bytes |

The [N53](runs/n53_ordinary/receipt.json) and
[N83](runs/n83_ordinary/receipt.json) receipts retain exact native field
operations, binary XOR counts, all stage intervals, raw solver status,
model/replay status, and memory. N53 spent 128,340 field multiplications,
221,490 squares, and 2,070 inversions in the new checks; N83 spent
126,201, 226,619, and 1,357 respectively. Q1461's normal-basis product
table also cost 2,809/2,915 N53 and 6,889/7,055 N83 multiplications/squares
at setup. Both runs had zero completed leaf-pair visits and zero SAT models.
These are costs of censored attempts, not work per successful decomposition.

## Matched controls and decision

Q1446 uses the same target-linked policy without this rule. Its matched
ordinary cells also reached their caps with zero relations. It measured
269,868 span checks at N53 and 62,000 at N83, while Q1462 reached its
earlier sparse-sum rejection states before a span check. The paths differ,
so the smaller Q1462 field-operation totals and memory do not establish a
speedup or a better successful-solve cost.

Q1445's matched-base pair table used the **same public point and exact base**
at each degree. It found one independently verified N53 four-point relation
after 500,000 target-independent table pair samples and 54,545 online query
pair samples. Its N83 sample cap found no relation. Its query law and work
unit differ from Q1462's SAT search, so these are matched-input outcomes,
not a wall-time ratio.

Q1462 demonstrates exact pruning on larger fixed-midpoint domains but no
ordinary relation or novel matrix row. The natural relation yield, cost per
useful row, successful N83 decomposition cost, and complete N131 `2^x`
remain unknown. The challenge gate stays closed. Further tuning of this
single fixed-midpoint no-pair check has weak support from these cells; a
next solver should couple many possible midpoint values to the target at
once, then repeat the frozen ordinary and rank-yield measurements.

Reproduce checks with the accepted Sage launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/validate_controls.py --check
python3 experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/verify_archive.py --check
```
