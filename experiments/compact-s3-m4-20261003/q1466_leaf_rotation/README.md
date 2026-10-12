# Q1466: diversify leaf decisions in the cached chained-S3 solver

Q1466 changes one decision rule in Q1465's target-linked four-summand
CaDiCaL solver. Each of the four leaves visits normal-basis coordinates
with a cyclic offset of `0`, `floor(n/4)`, `floor(n/2)`, or `floor(3n/4)`.
The target selector still goes first, and the leaf interleave remains
`0, 2, 1, 3`. This prevents all four leaves from receiving the same early
positive coordinate assignments. The CNFs, public targets, exact S3 root
cache, 250,000 pair cap, one-million conflict cap, and 60-second native wall
cap match Q1465. The [protocol](protocol.json) was committed before the
ordinary runs. Q1466 remains a `PDP4hybrid` proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`.

N53 uses curve `EC1N53Ckb1hf77aab617904`, the normal-basis weight-4 base
with `B=324,042` actual usable points and `K=3,057` folded columns. N83
uses `EC1N83Ckb1h876c2921cb64`, weight 6, `B=408,131,750`, and
`K=2,458,625`. The exact base digests, public targets, and workload IDs
are in the frozen protocol and receipts. The [planted controls](control_result.json)
recover independently verified four-point relations at both degrees.

## Frozen solver result

The [archive verifier](verification.json) checks source/input hashes,
receipts, cache accounting, models, and retained small snapshots. Each
cell reached the 60-second native cap without a model or verified relation.
Failed search work is included.

| Input | Q1465 / Q1466 exact checks | Q1466 actual S3 root evaluations | Q1466 field mul / sqr / inv | Q1466 peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 known-satisfiable selected preimage | 4 / 3 | 331,920 | 5,255,220 / 23,131,680 / 43,794 | 562,380,800 bytes | 0 |
| N53 ordinary full target | 4 / 3 | 331,920 | 5,255,220 / 23,131,680 / 43,794 | 628,834,304 bytes | 0 |
| N83 ordinary full target | 2 / 2 | 992,590 | 14,586,506 / 94,006,666 / 45,764 | 553,811,968 bytes | 0 |

The N53 and N83 first ordinary rejection states now have different leaf
support patterns from Q1464/Q1465. We froze a separate **post-result**
[serial-root audit](serial_audit_protocol.json) and replayed those two states
using Q1420's serial root oracle, without the cached batched-root code.
Both [audit runs](serial_audit_runs) found zero x-only target chains:

| Selected ordinary state | Pair candidates per side | Distinct midpoint x values | Fixed-state raw-target-x coverage ceiling |
| --- | ---: | ---: | ---: |
| N53 | 67,677 | 67,690 / 67,552 | `2^-19.91` |
| N83 | 249,719 | 249,674 / 249,784 | `2^-46.14` |

The ceiling is `2|M0||M1| / 2^n` for one fixed pair of midpoint sets.
It is only 0.054 bits higher at N53 and 0.037 bits higher at N83 than
Q1464's first-state ceilings. It does not bound target-adaptive SAT search
or the full support of the factor base. The independent audit covers two
selected states, not every large rejection. CPU wall times are exploratory
because this host has no isolation receipt.

The changed decision order did not construct an ordinary relation or
measure a novel matrix row. Natural useful-row yield, successful PDP cost,
and complete N131 `2^x` remain unknown; the `2^61` challenge gate stays
closed. This policy gives no evidence that deeper late-state pruning will
solve N83. The next solver needs a target-guided construction step while
the leaf domains are broad.

Reproduce the frozen checks with the accepted Sage launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1466_leaf_rotation/build.py --check
python3 experiments/compact-s3-m4-20261003/q1466_leaf_rotation/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1466_leaf_rotation/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1466_leaf_rotation/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/q1466_leaf_rotation/serial_audit_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```
