# Full ordinary N83 search with flattened Karatsuba XORs

The Q58 ordinary attempt applies the flattened Karatsuba circuit to the
same public point and exact shifted width-18 factor base as Q54. Its
target-dependent PDP interval reached the frozen 600-second wall cap
with stage status `bounded_unknown`. The full attempt overturns the
short Q57 pilot's apparent solver gain: the last CryptoMiniSat progress
line showed about 4.38 million conflicts near 599 seconds, while Q54
reached its five-million-conflict cap in 336.204 solver seconds.

The [protocol](protocol.json) fixes the curve, `df4396f4d8fc` public
workload, raw target choice zero, one CryptoMiniSat thread,
five-million-conflict cap, 600-second wall cap and 4 GiB sampled RSS
stop. The complete base has **B = 21,714,958 distinct usable subgroup
points before folding** and **K = 130,813 signed-Frobenius columns**.
Only recursive XOR materialization differs from Q54; the pilot source,
locked control and independent Sage replay are hash-bound in the
protocol. The target-generation scalar is represented only by a
SHA-256 commitment and is not read by the solver.

| Same base, point, solver and caps | Materialized Q54 | Flattened Q58 |
| --- | ---: | ---: |
| AND gates | 12,174 | 12,174 |
| CNF clauses | 105,251 | 105,251 |
| Variables | 75,783 | 40,905 |
| Native XOR rows | 62,937 | 28,059 |
| XOR literal occurrences | 224,049 | 615,561 |
| Solver status | conflict-cap `INDETERMINATE` | `external_timeout` |
| Solver seconds | 336.204 | 598.819 |
| Reported conflicts | 5,000,001 | null; last printed about 4.38 million |
| Sampled peak solver RSS | 219,742,208 B | 895,631,360 B |
| Ordinary stage status | `bounded_unknown` | `bounded_unknown` |

The denser XOR rows raise solver memory and erase the short pilot's
advantage over this longer boundary. The CPU host lacked a physical
isolation receipt, so both time rows remain exploratory. The result
does not promote Q58 as the faster ordinary decomposition method.
The [stage receipt](width18_ordinary.json) retains the raw solver
output, 5.2 MB raw XCNF archived as 1.1 MB gzip, memory samples and
exclusive phase costs;
its online interval was 600.012 seconds. The full pair-root index is
not allocated in this experiment.

The flattened circuit passed 32 fixed-seed field products and the
[Q57 locked relation control](../n83-geometric-m5-flatxor18-20261012/README.md).
[Independent Sage replay](sage_relation_replay.json) checks that group
relation through a separate polynomial field and records the ordinary
run's bounded status. The generic characteristic-two Karatsuba split
identity is Lean checked in the Q53 source; the complete flattened
circuit and S₃-to-curve bridge remain open Lean formalization
obligations.

[verify.py](verify.py) checks source, solver, base, cache, public target,
control, protocol, compressed formula and phase hashes. The checked
Sage launcher saved [runtime identity](sage_runtime_info.json) before
the run. Run the read-only receipt check from the repository root:

```sh
python3 experiments/n83-geometric-m5-flatxor-ordinary18-20261012/verify.py
```

The producer refuses to overwrite terminal evidence; use a fresh
output directory for a new run.
