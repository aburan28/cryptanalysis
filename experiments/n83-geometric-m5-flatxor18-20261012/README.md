# Flattened Karatsuba output XORs on the N83 width-18 base

Flattening recursive Karatsuba output combinations reduces the frozen
width-18 S₃ formula from **75,783 to 40,905 variables** and from
**62,937 to 28,059 native XOR rows**. It preserves 12,174 AND gates,
105,251 CNF clauses, the complete factor base and the public target.
The locked five-point control returns SAT and passes independent Sage
group replay.

The implementation represents each intermediate polynomial coefficient
as a parity bitset over already-created AND gates. It combines those
bitsets through the Karatsuba recursion, then materializes each final
field-product coordinate once. XORs needed as inputs to further AND
gates remain explicit. This makes the surviving XOR rows denser:
literal occurrences rise from 224,049 to 615,561, a cost measured in
the [shape screen](shape_screen.json).

| Same width-18 base and public target | Materialized Q54 | Flattened Q57 |
| --- | ---: | ---: |
| AND gates | 12,174 | 12,174 |
| CNF clauses | 105,251 | 105,251 |
| Variables | 75,783 | 40,905 |
| Native XOR rows | 62,937 | 28,059 |
| XOR literal occurrences | 224,049 | 615,561 |

The [Q57 protocol](protocol.json) binds the same exact shifted base
with **B = 21,714,958 usable subgroup points before folding** and
**K = 130,813 folded columns**, the same `df4396f4d8fc` public
workload and raw target choice zero, source and solver hashes, one
CryptoMiniSat thread, 4 GiB sampled RSS stop and 300,000-conflict cap.
The original pairwise XCNF raw SHA-256 exactly matches the archived Q54
formula. The [ABBA pilot](pilot_result.json) used the order original,
flattened, flattened, original:

| Arm | Formula | Solver seconds | Reported conflicts |
| ---: | --- | ---: | ---: |
| 0 | Original | 23.438 | 300,002 |
| 1 | Flattened | 15.843 | 300,003 |
| 2 | Flattened | 16.731 | 300,003 |
| 3 | Original | 17.740 | 300,002 |

Every arm printed `INDETERMINATE` at its conflict cap; the wrapper
retained exit-code 15 as `solver_failure`, and the pilot status is
`bounded_unknown`. The flattened arms were quicker than both bracketing
original arms in this exploratory local-host pilot. Host isolation is
unverified, so these CPU timings remain stage diagnostics. The
[Q58 follow-up](../n83-geometric-m5-flatxor-ordinary18-20261012/README.md)
runs one complete five-million-conflict ordinary attempt on the same
point and base.

The underlying characteristic-two Karatsuba split identity is Lean
checked in the [Q53 proof](../n83-geometric-m5-topology16-20261012/Karatsuba.lean).
The flattened circuit's implementation is checked by 32 fixed-seed
field products, the locked SAT control and
[independent Sage relation replay](sage_relation_replay.json). A Lean
proof of the complete coefficient-level implementation and its
S₃-to-curve bridge remains open.

[verify.py](verify.py) checks source, solver, base, public target,
control, both compressed formulas and all four raw solver outputs.
The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the pilot. Run the read-only receipt check from the repository
root:

```sh
python3 experiments/n83-geometric-m5-flatxor18-20261012/verify.py
```

The producers refuse to overwrite terminal evidence; use a fresh output
directory for a new run.
