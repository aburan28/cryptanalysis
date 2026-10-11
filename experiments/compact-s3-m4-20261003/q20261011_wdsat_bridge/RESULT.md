# Q1458: WDSat CNF-width compatibility preflight

The pinned WDSat CNF implication loader handles clauses of width one through
four. The frozen Q1419 balanced-S3 inputs contain longer clauses, so a direct
WDSat timing would omit constraints before search. The preflight counts those
clauses from the archived XCNF bytes and binds the finding to upstream commit
`61c6ff3f49445af2729274819edb27b85a89efc1`.

| Exact control formula | Clauses wider than four | Widths requiring lowering |
| --- | ---: | --- |
| N53 full lock | 22,772 | 9, 10, 53 |
| N53 free midpoints | 22,772 | 9, 10, 53 |
| N83 full lock | 4 | 83 |
| N83 free midpoints | 4 | 83 |

The adapter also replaced WDSat's quadratic static Gaussian undo-list with
dynamic row storage in a separate pinned checkout, leaving its search logic
intact. Source-bound build receipts and raw attempts are preserved. The two
N53 direct-input full-lock attempts reached search and hit the 60 s cap; the
N83 attempt failed during CNF buffer initialization. These are adapter
diagnostics, not solver comparisons on the exact input formulas. A macOS
address-space limit was unavailable, so receipts report observed child RSS
and label wall times exploratory.

Q1459 lowers each long clause into a width-four chain. Q1460 then shares
equivalent OR prefixes across clauses to reduce the auxiliary count.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_bridge/compatibility.py
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_bridge/validate.py --emit
```

The upstream source is [WDSat](https://github.com/mtrimoska/WDSat); it is
kept outside this repository under its GPL-3.0 license.
