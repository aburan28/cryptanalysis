# Exact N53 x-weight-four base and ordinary S3 solver screen

Q20261010182800 enumerated the complete cofactor-projected normal-x
weight≤4 factor base on `EC1N53Ckb1hf77aab617904`: **324,042 actual
usable subgroup points** before sign/Frobenius folding and **3,057
effective columns**. The sorted seven-byte key digest is
`ada6ba90db89a1980cda980ac276250dfe78dfc19e1b403f96eff75dda38eb6f`.
The independent other-lift/Frobenius audit reproduced every key and
per-weight count. The weight-three prefix reproduced Q1410's `B=24,062`,
`K=227`, and exact set digest. Enumeration took 41.56 exploratory wall
seconds on this shared host.

| Exact base on the same curve | Actual `B` | Folded `K` | Change in `B` from x-weight≤3 |
| --- | ---: | ---: | ---: |
| Q1410 x-weight≤3 | 24,062 | 227 | 1.00× |
| Q20261010182800 x-weight≤4 | 324,042 | 3,057 | 13.47× |

Q20261010184800 pinned Q1410's archived four-point witness inside the
weight-four formula. CryptoMiniSat returned `SAT` in 0.062 exploratory
wall seconds. The serialized native-XOR formula, signed full-point sum,
cofactor projection, and exact weight-four base columns passed an
independent audit. This verifies the encoding on a known decomposition;
the ordinary-query cell below supplies the search measurement.

Q20261010183500 rebuilt Q1410's weight-three ordinary formula to its
archived raw XCNF digest, then changed the four leaf bounds to weight
four. It uses the **same public point and ordinary workload**
`W74f2979b3e68`, the exact weight-four base, and the balanced three-link
S3 tree. The new formula has 27,130 variables, 100,472 CNF clauses,
795 native XOR rows, and 25,281 shared AND gates.

| Ordinary N53 cell | Status | Conflicts | Child CPU | Wall | Peak child RSS | Verified relations under cap |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Default CryptoMiniSat, x-weight≤4 | `BOUNDED_UNKNOWN` | 1,000,001 | 134.59 s | 323.78 s | 403.8 MB | 0 |

The independent formula/solver receipt auditor passed. Search reached
the conflict limit rather than the 1,200-second wall cap. Its zero
verified relations is a censored stage observation, not a natural-yield
rate or a rank measurement.

Q20261010184000 screened four solver settings on **the identical frozen
formula, base, public point, and binary**, with 100,000-conflict and
300-second wall limits per cell. The independent archive audit passed.

| Setting | Status | Conflicts | Child CPU | Wall | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| Negative polarity, automatic restart | `BOUNDED_UNKNOWN` | 100,002 | 19.49 s | 145.61 s | 222.2 MB |
| Positive polarity, automatic restart | `BOUNDED_UNKNOWN` | 100,002 | 10.00 s | 74.56 s | 99.0 MB |
| Negative polarity, Luby restart | `BOUNDED_UNKNOWN` | 100,002 | 19.64 s | 90.94 s | 325.0 MB |
| Negative polarity, geometric restart, seed one | `BOUNDED_UNKNOWN` | 100,002 | 14.76 s | 66.29 s | 280.3 MB |

The polarity choices change solver resource use, but none produced a
model within the common limit. These shared-host timings do not establish
a relation-finding speedup. The known-decomposition control and ordinary
query costs are recorded separately.

The archived Q1301 matched pair-table stage used this same public point
and workload with the **weight-three** base (`B=24,062`, `K=227`). It
recorded one verified four-point relation after 500,000 table samples
and 171,218 query samples, with 41.69 seconds of table work and 22.34
seconds of query work, plus 32.78 seconds of base setup. Those exploratory
stage costs are a useful control for Q1410 on the same base. The new
weight-four SAT cell changes the base, so its timing is not a paired
CPU-speedup comparison with that table. The pair-table receipt is
`runs/n53_ordinary_matched_pair_table.json` in the parent experiment.

The N131 exact x-weight-six base has `B=6,559,634,788` and `K=25,036,774`.
Under the frozen uniform-query relation-supply bound, obtaining `K`
rank rows requires at least `2^27.72` queries and leaves less than
`2^33.28` operations per query under a `2^61` total even with all other
costs set to zero. The present capped SAT cells do not supply an ordinary
relation rate, rank novelty, or a calibrated N131 PDP cost, so the
complete-solve `2^x` remains unknown. The next parameter search should
measure a larger x-base/leaf bound near the N131 weight-seven frontier
while explicitly charging its matrix growth, and reserve full-query
solver runs for variants that return verified relations at N53/N83.
