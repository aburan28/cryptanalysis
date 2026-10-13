# Six-summand decomposition on the larger N83 width-11 base

Q68 carries the two-coordinate width-11 factor base into the same six-leaf
S₃ decomposition stage and public target used by Q67. The new base has
**184,094 usable subgroup points before folding** and **1,109 signed-Frobenius
columns**. The planted six-point control is SAT and passes independent Sage
point, subgroup, base-membership, and group-sum replay. The ordinary
public-target query reached its 600-second wall cap with status
`bounded_unknown`.

| Frozen stage property | Q68 bits 26+38 | Q67 bit 81 |
| --- | ---: | ---: |
| Usable affine seeds | 1,109 | 1,097 |
| Actual subgroup points before folding, `B` | 184,094 | 181,936 |
| Signed-Frobenius columns, `K` | 1,109 | 1,096 |
| AND gates | 15,936 | 15,936 |
| CNF clauses | 139,353 | 139,425 |
| Native XOR rows | 79,276 | 79,768 |
| Variables | 96,026 | 96,518 |
| Ordinary status | `bounded_unknown` | `bounded_unknown` |
| Last raw progress | about 2.025 million conflicts | about 4.686 million conflicts |
| Sampled solver RSS peak | 104,038,400 bytes | 231,063,552 bytes |

Both protocols fix workload `df4396f4d8fc`, its one public point, the first
raw cofactor preimage, CryptoMiniSat, one solver thread, a five-million
conflict ceiling, and a 600-second wall cap. The **affine offset and its
exact factor base** are the comparison variables. Their SAT formulas also
differ in constant propagation and seed-validity clauses. The terminal
conflict fields are null after external timeout; progress counts above are
approximate readings of the retained raw logs. Both runs used a shared
local CPU, so the wall and RSS differences are exploratory stage evidence,
not a controlled speedup or relation-yield estimate.

The exact uniform-target six-subset first moment rises from
`20,831.181431...` to `22,358.376917...`, using the exact counts from the
[geometry census](../n83-geometric-two-shift11-20261012/README.md).
That combinatorial quantity does not determine the solver's yield on this
fixed target slice. The new [protocol](protocol.json),
[shape](shape.json), [control](six_point_control.json), and
[ordinary result](width11_m6_ordinary.json) bind the exact source, base,
solver, public input, and limits. Q68's 614.422-second target-dependent
PDP interval includes raw target-preimage construction, formula build and
write, the 598.991-second solver attempt, relation check, and residual
overhead. The raw XCNF and solver output are archived with hashes.

[Independent Sage replay](independent_sage_replay.json) reconstructs all
2,048 affine seeds in a separate polynomial-field model, checks the
1,109-seed validity bitset, and verifies the six planted projected points
and their group sum. The ordinary row is `no_relation_to_replay`. A first
verifier attempt used the old offset and failed at seed zero; its stderr
is preserved. The corrected verifier passed without changing the frozen
producer or ordinary-run evidence. The conditional six-leaf tree equation
is checked in [SixLeafTree.lean](SixLeafTree.lean); its
[#print axioms output](lean-build.txt) reports no axioms for either theorem.
The specific curve, S₃ circuit, and affine-domain bridge are checked by
the executed SAT and Sage controls; full Lean formalization remains open.

The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the workload. From the repository root, audit all receipts with:

```sh
python3 experiments/n83-geometric-m6-twoshift11-20261012/verify.py
```

The larger base is an exact geometry improvement at fixed width, while the
decomposition search is still capped on this target slice. The next
experiment should change the decomposition oracle or target-slice strategy
and measure verified ordinary relation yield and novel rank before final
factor-base log recovery.
