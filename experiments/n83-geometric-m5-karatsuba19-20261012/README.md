# Width-19 factor base in the N83 five-summand S3 decomposition

The exact shifted width-19 base contains **43,552,922 usable subgroup
points before folding** and **262,367 signed-Frobenius columns**. Its
ordinary five-summand decomposition on the frozen public N83 point
reached the five-million-conflict cap with stage status
`bounded_unknown`. The complete target-dependent PDP interval was
421.818 seconds, compared with 336.470 seconds for the width-18 base
under the same cap. The width-19 locked relation control returned SAT
and passed exact group replay.

| Same public target, solver and caps | Width 18 Q54 | Width 19 Q61 |
| --- | ---: | ---: |
| Usable base points B before folding | 21,714,958 | 43,552,922 |
| Folded columns K | 130,813 | 262,367 |
| Five-subset first moment under uniform-sum model | 16,641,170,632.3 | 540,101,636,092.1 |
| AND gates | 12,174 | 12,178 |
| CNF clauses | 105,251 | 105,263 |
| Variables | 75,783 | 75,813 |
| Native XOR rows | 62,937 | 62,958 |
| Reported solver conflicts | 5,000,001 | 5,000,002 |
| Solver seconds to conflict cap | 336.204 | 421.266 |
| Target-dependent PDP seconds | 336.470 | 421.818 |
| Sampled peak solver RSS | 219,742,208 B | 128,778,240 B |

The [protocol](protocol.json) fixes the exact [width-19 geometry](../n83-geometric-width19-20261012/README.md),
canonical-x cache, `df4396f4d8fc` public workload, raw target choice
zero, one CryptoMiniSat thread, five-million-conflict cap, 600-second
wall cap and 4 GiB sampled RSS stop. The only intended comparison
variable is the affine seed width and its resulting exact base. The
public point is fixed; the target-generation scalar appears only as a
SHA-256 commitment. The [stage receipt](width19_ordinary.json) retains
the compressed formula, raw solver outputs, memory samples and
exclusive phase costs. The full pair-root index is not allocated.

The [locked control](karatsuba_control.json) passed SAT and group
replay. [Independent Sage replay](sage_relation_replay.json) checks
that relation in a separate polynomial field representation and
records the bounded ordinary status. The earlier Q53 Lean theorem
checks the characteristic-two Karatsuba split identity; a full
formal bridge from this coefficient circuit through S3 to the curve
remains open.

The local CPU timings are exploratory because host isolation was
unverified. The combinatorial first moment counts potential subsets
under a uniform-sum model; it is not measured relation yield. The
ordinary run retained every failed attempt and its cap. The checked
Sage launcher saved [runtime identity](sage_runtime_info.json) before
measured work. Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-karatsuba19-20261012/verify.py
```
