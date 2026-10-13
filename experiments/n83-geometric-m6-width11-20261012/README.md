# Six-summand decomposition on the shifted N83 width-11 base

Q66 builds a five-link S₃ tree for six factor-base points on the exact
shifted width-11 base. This base has **181,936 usable subgroup points before
folding** and **1,096 signed-Frobenius columns**. A planted six-point control
returns SAT in 0.119 seconds and passes independent Sage point, subgroup,
base-membership, and group-sum replay. The ordinary public-target query
reached its 600-second wall cap with stage status `bounded_unknown`.

| Exact stage property | Q66 width-11 six-summand | Q54 width-18 five-summand |
| --- | ---: | ---: |
| Usable subgroup points, `B` | 181,936 | 21,714,958 |
| Folded columns, `K` | 1,096 | 130,813 |
| Uniform-target subset first moment | `C(B,6)/r = 20,831.181431...` | `C(B,5)/r = 16,641,170,632.3` |
| AND gates | 15,936 | 12,174 |
| CNF clauses | 133,719 | 105,251 |
| Native XOR rows | 79,768 | 62,937 |
| Ordinary query status | `bounded_unknown` | `bounded_unknown` |
| Solver stop | 600-second external timeout | 5,000,001 conflicts |

The first moment is an exact uniform-target combinatorial diagnostic for the
complete base. It does not estimate solver success on the frozen target or
novel relation rank. Q66 changes both arity and factor base relative to Q54;
the table is a resource and stage comparison, not a controlled single-variable
timing comparison.

The six leaves form three pairs, followed by two joins:
`u0=P0+P1`, `u1=P2+P3`, `u2=P4+P5`, `u3=u0+u1`, and
`T=u3+u2`. Each link uses the pinned power-basis Karatsuba S₃ circuit.
The first leaf is one affine seed in `gamma_82+W_11`; the other five
independently choose a seed and one of 83 Frobenius powers. This pilot fixes
the first raw cofactor preimage of the same public target as Q54, without
rotating that target. It therefore tests one declared target slice.

The [geometry source](../koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER/README.md)
and its independent Sage replay enumerate every width-11 seed. The
[materialization receipt](materialization.json) checks all 1,096 canonical-x
cache entries, the original key file, and 258 reconstructed points. The
[shape receipt](shape.json), [protocol](protocol.json), and
[ordinary result](width11_m6_ordinary.json) bind the exact base, public
point, source, solver and limits. The 601.355-second target-dependent PDP
interval includes raw target-preimage construction, formula build and write,
the 598.980-second solver attempt, relation check, and residual overhead.
The last progress line showed about 3.866 million conflicts, while the
terminal `conflicts_reported` field is null because the process timed out.
Peak sampled solver RSS was 202,883,072 bytes. These local CPU times are
exploratory on a shared host.

[Independent Sage replay](independent_sage_replay.json) verifies all six
planted points on `y²+xy=x³+1` over the separate polynomial-field model,
their exact tree sums, cofactor projections, prime-order subgroup checks,
and membership in the width-11 canonical-x set. The ordinary row is recorded
as `no_relation_to_replay`. The conditional tree-to-six-sum group equation
is checked in [SixLeafTree.lean](SixLeafTree.lean); its
[#print axioms output](lean-build.txt) reports no axioms for either theorem.
The Lean module assumes associativity explicitly. Formal definitions
connecting the specific field, curve, S₃ equations, and base policy to that
generic group theorem remain open; the executed instance is checked by
native SAT controls and independent Sage arithmetic.

The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before measured work. Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m6-width11-20261012/verify.py
```

This result leaves the smaller six-summand pipeline at a bounded solver
stage. A next decomposition test should change the solver or split strategy
and measure ordinary relation yield and novel rank on this same exact base
before attempting complete factor-base log recovery.
