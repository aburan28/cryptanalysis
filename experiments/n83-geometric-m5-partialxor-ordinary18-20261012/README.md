# Full ordinary N83 search with length-21 Karatsuba XOR materialization

The Q60 full ordinary attempt reached the five-million-conflict cap in
337.078 solver seconds on the same public point and exact width-18 base
as Q54. The original pairwise circuit reached that cap in 336.204
solver seconds. Both stage statuses are `bounded_unknown`. The
length-21 circuit uses fewer variables and XOR rows but more XOR
literal occurrences and solver memory; its short pilot advantage did
not persist through this full attempt.

| Same base, point, solver and caps | Original Q54 | Partial Q60 |
| --- | ---: | ---: |
| Usable base points before folding | 21,714,958 | 21,714,958 |
| Signed-Frobenius columns | 130,813 | 130,813 |
| AND gates | 12,174 | 12,174 |
| CNF clauses | 105,251 | 105,251 |
| Variables | 75,783 | 45,162 |
| Native XOR rows | 62,937 | 32,316 |
| XOR literal occurrences | 224,049 | 292,011 |
| Solver seconds to conflict cap | 336.204 | 337.078 |
| Reported conflicts | 5,000,001 | 5,000,001 |
| Sampled peak solver RSS | 219,742,208 B | 295,321,600 B |

The [protocol](protocol.json) freezes `df4396f4d8fc`, raw target
choice zero, the base and cache digests, one CryptoMiniSat thread,
five-million-conflict cap, 600-second wall cap and 4 GiB sampled RSS
stop. The public point is fixed; the target-generation scalar appears
only as a SHA-256 commitment. The [stage receipt](width18_ordinary.json)
retains the formula, raw solver outputs, memory samples, exclusive
phase costs and 337.605-second target-dependent PDP interval. The
full pair-root index is not allocated in this experiment.

The [Q59 locked control](../n83-geometric-m5-partialxor18-20261012/karatsuba_control.json)
returned SAT with group replay. [Independent Sage replay](sage_relation_replay.json)
checks that relation in a separate field representation and records
the bounded ordinary status. The Q53 Lean theorem checks the
characteristic-two Karatsuba split identity; the coefficient-level
circuit and S3-to-curve bridge remain open formalization obligations.

These local CPU timings are exploratory because physical host
isolation was unverified. The equal-conflict full attempt supports a
formula-size tradeoff, without a solver-time improvement at this cap.
The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the run. Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-partialxor-ordinary18-20261012/verify.py
```
