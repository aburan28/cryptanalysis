# Partial Karatsuba XOR materialization on the N83 width-18 base

Materializing each Karatsuba recursion output at length 21 gives a
middle ground between the original pairwise circuit and complete XOR
flattening. On the same exact shifted width-18 base and public point,
the circuit has 45,162 variables, 32,316 native XOR rows, and 292,011
XOR literal occurrences. Its 12,174 AND gates and 105,251 CNF clauses
match the original circuit. The locked five-point relation control
returns SAT and passes group replay.

| Circuit | Variables | XOR rows | XOR literal occurrences |
| --- | ---: | ---: | ---: |
| Original pairwise Q54 | 75,783 | 62,937 | 224,049 |
| Partial length-21 Q59 | 45,162 | 32,316 | 292,011 |
| Fully flattened Q57 | 40,905 | 28,059 | 615,561 |

The [shape screen](shape_screen.json) also records recursion cutoffs 0,
2, 3, 6, 11, and 42. The [Q59 protocol](protocol.json) freezes the
length-21 pilot on the same `df4396f4d8fc` public workload, target
choice zero, **B = 21,714,958 usable subgroup points before folding**,
**K = 130,813 signed-Frobenius columns**, one CryptoMiniSat thread,
one-million-conflict cap, 180-second wall cap per arm and 4 GiB sampled
RSS stop. The comparison changes only the XOR materialization policy.

The [ABBA pilot](pilot_result.json) ran the original, partial, partial,
original formula order:

| Arm | Circuit | Solver seconds | Reported conflicts |
| ---: | --- | ---: | ---: |
| 0 | Original | 106.398 | 1,000,002 |
| 1 | Partial length-21 | 60.140 | 1,000,001 |
| 2 | Partial length-21 | 48.144 | 1,000,001 |
| 3 | Original | 71.011 | 1,000,002 |

All four arms printed `INDETERMINATE` at the conflict cap; the wrapper
records the solver's exit code 15 as `solver_failure`. The pilot status
is `bounded_unknown`. These local CPU times are exploratory because
host isolation was unverified. The [Q60 full attempt](../n83-geometric-m5-partialxor-ordinary18-20261012/README.md)
tests whether the apparent stage gain persists at five million conflicts.

The first locked-control invocation accidentally selected target choice
zero while the pinned relation requires choice 267. Its raw `UNSAT`
output and wrapper failure are retained as
[`choice0_control_failure.json`](choice0_control_failure.json) with the
compressed formula and stdout/stderr. After passing the selected choice
through the wrapper, the [locked control](karatsuba_control.json) returned
SAT and exact group replay. [Independent Sage replay](sage_relation_replay.json)
checks the group relation through the separate polynomial field. The
shape screen predates the wrapper argument correction; the formula
shape for target choice zero is unchanged and is reproduced by the
frozen full attempt. The Q53 Lean theorem checks the underlying
characteristic-two Karatsuba split identity. A coefficient-level Lean
proof of this circuit and the S3-to-curve bridge remains open.

The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before measured work. Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-partialxor18-20261012/verify.py
```
