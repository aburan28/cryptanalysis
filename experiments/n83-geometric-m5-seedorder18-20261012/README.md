# Seed-ordered free leaves in the N83 width-18 circuit

Q65 orders the four interchangeable free leaves by their 18-bit affine seed
coordinates. The constraint adds **48 AND gates, 198 CNF clauses, and 51
native XOR rows** to the frozen Q54 five-summand Karatsuba formula. A planted
five-point relation remains SAT and passes independent Sage group replay.
The ordinary public-target attempt reached 5,000,002 reported conflicts
with stage status `bounded_unknown` under the same five-million-conflict
setting as Q54.

| Same shifted width-18 base and public point | Q54 | Q64 raw-x order | Q65 seed order |
| --- | ---: | ---: | ---: |
| Usable subgroup points before folding, `B` | 21,714,958 | 21,714,958 | 21,714,958 |
| Signed-Frobenius columns, `K` | 130,813 | 130,813 | 130,813 |
| AND gates | 12,174 | 12,417 | 12,222 |
| CNF clauses | 105,251 | 106,229 | 105,449 |
| Native XOR rows | 62,937 | 63,183 | 62,988 |
| Ordinary target status | `bounded_unknown` | `bounded_unknown` | `bounded_unknown` |
| Solver stop | 5,000,001 conflicts | 600-second timeout | 5,000,002 conflicts |
| Local solver interval | 336.204 s | 599.622 s | 444.177 s |

The four free leaves share one domain, so any valid five-point relation can
be permuted into nondecreasing seed order. The comparator operates directly
on each leaf's 18 primary seed variables. The independent
[comparator control](comparator_control.json) checked `3 ≤ 5` SAT, `7 ≤ 7`
SAT, and `9 ≤ 8` UNSAT against the actual XCNF encoder. The
[planted control](ordered_control.json) pins all five leaves and internal
S₃ coordinates, returns SAT, and passes exact signed/cofactor group replay.
The conditional adjacent-swap equations are checked in
[FreeLeafSymmetry.lean](FreeLeafSymmetry.lean) with the pinned Lean 4.34.1
[toolchain](lean-toolchain); the [axiom audit](lean-build.txt) reports none
for all three declarations. The curve/factor-base closure and circuit bridge
are checked computationally and remain an open Lean formalization step.

The [protocol](protocol.json) fixes the Q54 curve, public point, workload
`df4396f4d8fc`, shifted width-18 base, canonical-x cache, CryptoMiniSat
binary, one thread, five-million-conflict setting, 600-second wall cap, and
4 GiB sampled solver RSS stop. The target-generation scalar appears only as
a hash commitment. The [ordinary receipt](width18_ordinary.json) retains
the solver's `solver_failure` exit label for CryptoMiniSat's conflict-cap
`INDETERMINATE`, while the stage remains `bounded_unknown`. It binds raw
stdout/stderr, compressed XCNF, memory sample, and exclusive target-dependent
phases. [Independent Sage replay](sage_relation_replay.json) verifies the
planted point relation and records `no_relation_to_replay` for the ordinary
row. The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the run.

The local 336- and 444-second intervals came from separate shared-host
runs, so their ratio is exploratory. The exact circuit size reduction from
Q64 to Q65 is reproducible; neither ordinary attempt supplied a verified
relation. The next method should improve relation search by changing the
S₃ decomposition or solver strategy, rather than adding another leaf-order
comparator.

Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-seedorder18-20261012/verify.py
```
