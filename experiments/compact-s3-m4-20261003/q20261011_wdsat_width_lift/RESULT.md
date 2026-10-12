# Q1459: exact width-four CNF lowering for WDSat

The per-clause Tseitin chain turns each archived Q1419 long CNF clause into
clauses of width at most four while preserving every XOR row and original
variable ID. Archived full-lock assignments extend to satisfying assignments
for both N53 and N83 transformed formulas. Exhaustive single-clause checks
cover widths five through ten over 14,016 full assignments.

| Degree | Added variables | Transformed rows | Full-lock control |
| ---: | ---: | ---: | --- |
| 53 | 68,404 | 169,586 | Native macOS loader failed before search; binary has 2.636 GB `__DATA` segment |
| 83 | 160 | 191,833 | WDSat plain SAT; transformed and original XCNF models replayed, 10.435 s exploratory |

The N53 clauses share long prefixes. Q1460 reuses logically equivalent
prefix variables and reduces the N53 auxiliary count to 268, enabling the
full-lock control to run. Q1459's N83 result remains a correctness control;
the free-midpoint search gate belongs to Q1460.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_width_lift/validate.py
```
