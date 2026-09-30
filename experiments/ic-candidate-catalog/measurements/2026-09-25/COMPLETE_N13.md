# Complete N13 IC candidate versus paired rho

This follow-up promotes a fully specified toy candidate derived from the
`Q1` axes: N13, the frozen six-point base, four summands, SAT PDP, first
verified witness, Gaussian relation-matrix solving, and a 50 ms per-query
limit. Its exact method is an **explicit four-sum selector CNF**. The earlier
N13 SAT stage receipts used a chained-S3 encoding and are not measurements of
this candidate. The 1,000 `Q` rows remain proposals; this exact variant has
its own [candidate manifest](complete_n13_sat_candidate.json):

`IC1N13Ckb1fb6PDP4satRCsampleLAgaussTDdescentISO0h6adc50caf2cb`

The source curve, field representation, generator, subgroup, base points,
solver binary hash, code hashes, algorithms, limits, and absent isogeny route
are pinned in the manifest. The [raw receipt](complete_n13_sat_receipt.json)
and [contract-v2 run rows](complete_n13_sat_runs.jsonl) retain every relation
query and target attempt. The [runner](complete_n13_sat.py) refuses to
overwrite its outputs. The [read-only verifier](verify_complete_n13.py)
recomputes the IDs and source hashes, independently enumerates the sumset
using the separate reference arithmetic, replays the factor-log relations,
and checks every recovered target scalar and run row.

## Preparation and accounting boundary

The exact base contains six distinct subgroup points in two signed-Frobenius
columns. Its 126 unordered four-point multisets cover exactly 84 of the
2,002 nonidentity subgroup points. The reusable CNF has one selector per
multiset; a target's 27 encoded bits are supplied as SAT assumptions. This
explicit sumset is target-independent preparation. The collector then drew
39 ordinary known-scalar subgroup queries: 37 were outside the exact
four-sum support, two gave verified relations, and those two raised the final
matrix rank to two. The observed within-budget relation yield was 2/39,
or 5.13%, with a Wilson 95% interval of 1.42–16.89%. Both recovered factor
logs were independently replayed.

One preparation run took **38.796 ms** before the first target. Its measured
subphases included curve setup 0.820 ms, base construction/folding 4.319 ms,
four-sum enumeration 2.268 ms, CNF construction 2.626 ms, ordinary-query
generation 3.490 ms, complete PDP calls 0.986 ms, relation checks 0.289 ms,
Gaussian row solving 0.028 ms, and factor-log certificates 1.363 ms. The preparation
wall total also includes harness, hashing, and orchestration outside these
subphase timers. It is supplementary and is **not** added to the target
online metric. No fully allocated operation-count total is claimed.

Each target was a distinct public point generated from a fixture scalar
outside both timed intervals, absent from the 39 preparation queries. Only
the point entered either solver. The IC online clock began with its first
target-dependent shift/query and ended after scalar recovery and an
independent reference-arithmetic replay. It included all unsuccessful SAT
queries, group operations, relation checking, and descent. Rho received the
same point and curve implementation; its clock included walk setup,
restarts, collision resolution, and scalar replay. Both ran in one process
on this macOS arm64 host; SAT used one native thread. The five exclusive IC
online phase times sum exactly to each saved `online_wall_ns`.

## Paired one-target results

The first completed workload is the primary result: **IC 8.991 ms**, **rho
2.207 ms**, and `rho/IC = 0.245×`. Thus IC took about 4.07 times as long on
that point. After it completed, 19 further distinct one-target workloads
used the same ready index and factor logs. They are separate paired runs,
not a batch average or a shared-setup speedup.

| Target | IC target queries | IC online ms | Rho online ms | Rho / IC |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 52 | 8.991 | 2.207 | 0.245 |
| 2 | 25 | 4.197 | 1.863 | 0.444 |
| 3 | 2 | 0.835 | 2.196 | 2.631 |
| 4 | 5 | 2.973 | 2.221 | 0.747 |
| 5 | 30 | 4.483 | 1.566 | 0.349 |
| 6 | 17 | 3.257 | 1.295 | 0.398 |
| 7 | 9 | 1.695 | 2.997 | 1.768 |
| 8 | 51 | 7.590 | 2.573 | 0.339 |
| 9 | 67 | 10.538 | 3.561 | 0.338 |
| 10 | 57 | 9.416 | 3.069 | 0.326 |
| 11 | 16 | 3.450 | 2.902 | 0.841 |
| 12 | 33 | 4.921 | 3.276 | 0.666 |
| 13 | 8 | 1.741 | 2.579 | 1.481 |
| 14 | 14 | 2.454 | 0.845 | 0.344 |
| 15 | 45 | 6.956 | 2.054 | 0.295 |
| 16 | 14 | 3.665 | 1.621 | 0.442 |
| 17 | 21 | 3.319 | 1.454 | 0.438 |
| 18 | 18 | 3.006 | 2.047 | 0.681 |
| 19 | 44 | 6.748 | 1.527 | 0.226 |
| 20 | 11 | 2.024 | 3.195 | 1.579 |

All 20 IC and rho scalars were verified. IC was faster on **4/20** points.
The median of the **20 paired ratios** was **0.440×**. A 10,000-resample
percentile bootstrap of those paired ratios, with seed 98103, gave a 95%
interval of **0.342–0.714×**. The separate medians were 3.558 ms for IC
and 2.202 ms for rho; their quotient is not used as the paired estimator.
Median process CPU times were 3.302 ms and 2.099 ms respectively. Wall time
includes scheduling noise, and each target was timed only once, so the
bootstrap interval reflects variation across targets and these runs rather
than an independently repeated hardware-timing study.

The result is a complete **toy-field** comparison. Its 2,003-element DLP
subgroup and exhaustively materialized 126-tuple index make it unsuitable
as evidence for N53 or ECC2K-130 performance. It uses no isogeny; the
catalog's isogeny proposals still require explicit maps and transport proof.

## Reproduce and verify

From the repository root, run the saved receipt verifier and analyzer:

```sh
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/ic-candidate-catalog/measurements/2026-09-25/verify_complete_n13.py
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/ic-candidate-catalog/analyze.py experiments/ic-candidate-catalog/measurements/2026-09-25/complete_n13_sat_runs.jsonl
```

To remeasure, use a separate copy of the workspace with the three saved
output files removed. The runner deliberately will not replace these raw
receipts.
