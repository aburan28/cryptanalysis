# Q1490: ordinary N53 relation to raw-window S3 witness

Q1488 found one verified four-point relation for Q1482's ordinary N53 public
target on Q1481's exact window-orbit factor base. Q1490 checks whether that
relation has a representation in the raw variables used by Q1482's compact
four-summand search. It is a **known-witness correctness control**: Q1488's
answer is supplied to the bridge. It does not measure an unpinned solver.

The exact curve is `EC1N53Ckb1hf77aab617904`. The Q1481 base has
430,360 distinct usable subgroup points before folding and 4,060 folded
columns, with enumerated-set SHA-256
`42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5`.
This remains proposal `Q1490`, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`. No isogeny route or end-to-end IC candidate is asserted.

The [design](design_protocol.json) and [R1 protocol](protocol.json) froze the
Q1488 relation, Q1482 ordinary target and target-preimage list, Q1481 key
archive, source, and checked Sage runtime. R1 stopped at a source preflight
assertion before scanning raw representatives. Its [failure receipt](runs/r1/failure.json)
records the error: Q1488's signed-Frobenius key packs canonical x and y
cycle coordinates, while Q1481's archive holds x-only keys. The
[recovery design](design_recovery.json) and [R2 protocol](recovery_protocol.json)
froze the explicit `full_key >> 53` conversion and kept every mathematical
input unchanged before R2 ran.

The [R2 receipt](runs/r2/bridge_result.json) passes these checks:

- All four projected points are distinct signed-Frobenius columns in the
  exact Q1481 archive. Their four raw lifts have nonzero x coordinates in
  cyclic 14-coordinate windows and project back to the Q1488 points.
- The four projected points sum to the unchanged ordinary public target.
  The four raw lifts sum to target preimage **141 of 428** in Q1482's
  frozen ordinary target list.
- Both raw pair midpoints and the raw target satisfy all three chained
  `S3` equations and independent root-membership checks.

This establishes that the known ordinary Q1488 relation lies in the
mathematical domain of Q1482's window and three-link S3 formulation. It
does not prove that a particular CNF encoding accepts the witness, and it
does not provide a natural relation rate, successful unpinned PDP cost,
N83 result, novel-rank rate, or complete N131 `2^x`.

Reproduce the frozen checks with the repository's accepted Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1490_ordinary_witness_bridge/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1490_ordinary_witness_bridge/freeze_recovery.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1490_ordinary_witness_bridge/bridge_v2.py --check
```

The next correctness gate is to pin these exact raw leaf and midpoint
coordinates, plus target-preimage index 141, into the frozen Q1482 ordinary
CNF and verify a satisfying assignment. Search-cost measurement still
requires an unpinned ordinary query.
