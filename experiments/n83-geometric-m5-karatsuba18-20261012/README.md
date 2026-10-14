# Width-18 factor base with the N83 Karatsuba S₃ circuit

The shifted width-18 base contains **21,714,958 distinct usable subgroup
points before sign/Frobenius folding** and **130,813 folded columns**.
The Karatsuba five-summand formula for the same public point has 12,174
AND gates and 105,251 CNF clauses, only 36 and 108 more than the
width-16 formula. A locked five-point control returns SAT and passes
exact group replay in independent Sage. The ordinary Q54 search reached
the frozen five-million-conflict cap with stage status `bounded_unknown`.

The [protocol](protocol.json) holds the curve, target point, raw cofactor
preimage choice zero, field multiplier, one CryptoMiniSat thread,
five-million-conflict cap, 600-second wall cap and 4 GiB sampled solver
RSS stop fixed against [Q53 width 16](../n83-geometric-m5-topology16-20261012/README.md).
Its factor-base variable is the shifted affine dimension: width 18
versus width 16. The [exact geometry receipt](../n83-geometric-width17-18-20261012/frontier.json)
and [independent full-seed Sage replay](../n83-geometric-width17-18-20261012/independent_sage_replay.json)
bind the new base. The [canonical-x cache](materialization.json) contains
one 11-byte entry for every key, 1,438,943 bytes total; all entries are
distinct, and 259 keys were checked by point reconstruction and a direct
83-power Frobenius minimum.

| Same public target and multiplier | Width 16, Q53 | Width 18, Q54 |
| --- | ---: | ---: |
| Usable points B | 5,419,568 | 21,714,958 |
| Folded columns K | 32,648 | 130,813 |
| Five-subset combinatorial first moment | 16,114,307.7 | 16,641,170,632.3 |
| AND gates | 12,138 | 12,174 |
| CNF clauses | 105,143 | 105,251 |
| Native XOR rows | 62,870 | 62,937 |
| Solver seconds at 5,000,001 conflicts | 443.401 | 336.204 |
| Sampled peak solver RSS | 231,686,144 B | 219,742,208 B |
| Ordinary stage status | `bounded_unknown` | `bounded_unknown` |

The first moments are exact `binom(B,5)/r` calculations under a
uniform-sum model. They do not substitute for observed relation yield or
matrix rank. The last two solver-cost rows are exploratory local-host
diagnostics; no host isolation receipt qualifies them as controlled CPU
speedups. Q54's target-dependent PDP interval was 336.470 seconds, with
exclusive phase costs in [width18_ordinary.json](width18_ordinary.json).
CryptoMiniSat printed `INDETERMINATE` at the conflict cap; the wrapper's
exit-code 15 label `solver_failure` is retained in the attempt, while the
stage classification is `bounded_unknown`.

The full pair-root plus cached-XY layout for this base would require
136.35 TB under the frozen `83K²` state law, far above the declared
8 GiB index memory cap. This SAT stage uses the small canonical-key and
canonical-x caches instead. The next [Q55 portfolio](../n83-geometric-m5-target-portfolio18-20261012/README.md)
tests multiple fixed raw-target slices under one total cap.

[verify.py](verify.py) checks source, solver, base, cache, control,
protocol, phase and compressed-formula hashes. [Independent Sage
replay](sage_relation_replay.json) checks the locked control against a
separately constructed polynomial field and curve. The generic
Karatsuba split identity is Lean checked in the Q53 source; the exact
width-18 circuit is additionally checked by 32 fixed-seed field
products and the locked SAT control. The full circuit and S₃-to-curve
bridge remain open Lean formalization obligations.

Run read-only receipt checks from the repository root:

```sh
python3 experiments/n83-geometric-m5-karatsuba18-20261012/verify.py
```

The checked repository Sage launcher produced
[sage_runtime_info.json](sage_runtime_info.json). Producers and the
independent Sage verifier refuse to overwrite terminal evidence; use a
fresh output directory to reproduce a new run.
