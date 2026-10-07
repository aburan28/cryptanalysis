# Q1491: exact ordinary N53 witness in Q1482's frozen CNF

Q1490 reconstructed Q1488's verified ordinary N53 relation in the raw
cyclic-window and chained-S3 variables. Q1491 tests the next correctness
gate: whether the **unchanged Q1482 ordinary CNF** accepts that witness.
This is an oracle-assisted pinned control, not an ordinary unpinned
decomposition measurement.

The [pre-registered design](design_protocol.json) freezes the exact curve
`EC1N53Ckb1hf77aab617904`, Q1481's 430,360 usable subgroup points and
4,060 folded columns, the Q1490 R2 witness, Q1482's 215,803-clause
ordinary CNF and target files, the Q1480 native solver binary, checked Sage
runtime, and limits. Q1491 remains a proposal with `candidate_id: null`,
`run_id: null`, and `isogeny: "none"`.

The [frozen protocol](protocol.json) pins exactly 327 variables: four
53-bit leaf x coordinates, two 53-bit pair midpoint x coordinates, and
nine bits selecting Q1482 target preimage 141 of 428. The runner appends
those unit clauses to a byte-identical original CNF body. It checks the
original CNF SHA-256, target file, variable map, source and binary hashes
before launching the frozen native solver. The pinned CNF is generated at
runtime and its digest is retained in the receipt.

The [R1 receipt](runs/r1/receipt.json) records `PASS`: native SAT exit 0,
zero conflicts, two decisions, 51,155 SAT propagations, 209 field
multiplications, 1,236 squarings, 18 inversions, and five S3 root calls.
The native process took 0.524 seconds on this unisolated host. The archived
[model](runs/r1/solver.model.txt) satisfies both the original and pinned
CNFs. Independent replay verifies four distinct folded columns and the
unchanged public target, using target preimage 141. The process time and
operation counts are **pinned-control diagnostics**; they do not estimate
the cost of an unpinned solve.

This removes one possible explanation for Q1482's ordinary N53 timeout:
the frozen CNF does contain the known Q1488 relation. It does not establish
that the current search policy can find it without pins. There is still no
successful N83 ordinary compact solve, measured natural yield or novel-row
cost, or complete N131 `2^x`.

Reproduce the frozen checks with the repository launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1491_ordinary_cnf_witness/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1491_ordinary_cnf_witness/run.py --check
```
