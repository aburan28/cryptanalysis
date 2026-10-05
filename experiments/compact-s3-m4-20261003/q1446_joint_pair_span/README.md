# Q1446: target-linked span checks on both sparse pairs

Q1446 changes the compact chained-`S3` search order. It selects the public
target preimage, fixes the two pair-intermediate x coordinates under the
final `S3` link, then interleaves bit decisions across **all four** sparse
leaves. While both leaves of either pair are still partial, it applies
Q1432's cached sound bilinear-span necessary condition to that pair. The
same condition now runs on pair 0 and pair 1 before either pair is completed.
No `S5` polynomial is expanded.

For each pair, if the fixed intermediate and fixed leaf bits make the
bilinear-span relaxation inconsistent, every completion of those leaf bits
fails that pair's exact `S3` equation. The emitted SAT clause is guarded by
the complete fixed intermediate and the fixed bits of that pair. The final
`S3` link constrains the two intermediates to the target, so the conjunction
is a sound target-conditioned necessary condition on **both** pairs. It is
not sufficient for a four-point relation; a returned model still requires
independent curve and subgroup replay.

The [frozen protocol](protocol.json) pins Q1438's exact N53 W≤4 and N83
W≤6 curves, bases, public targets, CNFs, variable maps, and target-preimage
lists. N53 is `EC1N53Ckb1hf77aab617904`, with actual `B=324,042` and
folded `K=3,057`. N83 is `EC1N83Ckb1h876c2921cb64`, with actual
`B=408,131,750` and folded `K=2,458,625`. The exact base digests are in the
protocol. The method is proposal `Q1446` with `candidate_id: null`,
`isogeny: "none"`, and point-decomposition stage code `PDP4hybrid`; it is
not a complete `IC1` pipeline.

The [pre-run validation](validation.json) independently replays known
Q1438 four-point controls at N53 and N83. A separate N53 ordinary-target
control leaves 14 bits free in each leaf and invokes the span filter on
both pairs while preserving its archived witness. These are correctness
controls, not ordinary-query cost or natural-yield samples. The protocol
was committed before ordinary N53/N83 executions.

Each ordinary cell has a one-million-conflict limit, a 60-second internal
wall cap, and a 75-second outer safeguard. The runner charges target-
dependent formula construction, native solving, and relation replay in its
online **stage** interval. It records native field operation counts, SAT
decisions, per-pair span checks and rejections, raw failures, and peak child
RSS. CPU wall times on this host are exploratory without an isolation
receipt. One ordinary relation would be a solver gate; natural yield and
cost per novel rank row require a fresh frozen panel.

## Reproduction

All Sage jobs must use the checked repository launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1446_joint_pair_span/build_solver.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1446_joint_pair_span/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1446_joint_pair_span/run_stage.py --degree 53
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1446_joint_pair_span/run_stage.py --degree 83
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1446_joint_pair_span/verify_archive.py --check
```

The runner refuses to overwrite measured rows. A fresh checkout needs a
locally rebuilt native binary from the pinned source and dependency hashes,
plus an accepted checked Sage runtime receipt, before reproducing the
ordinary cells.

## Frozen ordinary result

The [archive audit](verification.json) rebuilds both exact CNFs, checks the
source and output hashes, and independently replays 16 sampled span
rejections at each degree. The samples include both pairs. No sampled false
rejection occurred. Both cells reached the native 60-second wall cap with no
model and no relation; they are censored lower bounds on unsuccessful
attempts.

| Degree | Pair-0 span checks / rejections | Pair-1 span checks / rejections | Final roots; completed pair visits | Field mul / sqr / inv | Charged stage wall | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 265,256 / 257,392 | 4,612 / 4,237 | 1; 0 | 1,920,918 / 5,269,709 / 70,371 | 62.125 s | 885,391,360 bytes |
| N83 | 56,491 / 55,977 | 5,509 / 5,393 | 1; 0 | 2,177,153 / 15,323,711 / 145,376 | 63.002 s | 288,096,256 bytes |

The charged stage wall includes formula construction, native solving,
artifact materialization, and replay. The native solver itself spent about
60 seconds in each cell. The source receipts retain additional SAT decisions,
cache work, exact per-phase intervals, memory, and raw failures.

The new order successfully applies both sparse-pair filters before either
pair is complete, but it spends the cap exploring leaf assignments under a
single target-linked intermediate choice. It has not measured the cost of a
successful ordinary decomposition. More filtering of leaves under one
intermediate is unlikely to fix the observed coverage bottleneck by itself;
the next method needs to constrain or process many intermediate choices
together without enumerating target-independent first pairs. Q1445's
matched-base pair table remains the comparison. Natural relation yield,
novel rank, cost per useful row, and complete N131 `2^x` remain unknown; no
challenge run is admitted.
