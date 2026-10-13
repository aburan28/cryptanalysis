# Exact valid-seed clauses for the N83 six-summand base

Q67 adds an exact rational-point seed filter to the six-summand S₃ tree on
the shifted width-11 N83 factor base. Independent Sage arithmetic finds
**1,097 usable seeds and 951 invalid seeds** among the 2,048 affine inputs.
The filter forbids each invalid 11-bit assignment at each of six leaves,
adding 5,706 CNF clauses without changing the field circuits or XOR rows.
The planted six-point control is SAT and passes independent point, subgroup,
base-membership, and sum replay. The fixed ordinary public-target slice
reached its 600-second cap with status `bounded_unknown`.

| Frozen stage property | Q67 exact seed filter | Q66 unrestricted seeds |
| --- | ---: | ---: |
| Actual usable subgroup points before folding, `B` | 181,936 | 181,936 |
| Signed-Frobenius columns, `K` | 1,096 | 1,096 |
| Valid / invalid affine seeds | 1,097 / 951 | 1,097 / 951 |
| AND gates | 15,936 | 15,936 |
| CNF clauses | 139,425 | 133,719 |
| Native XOR rows | 79,768 | 79,768 |
| Ordinary query status | `bounded_unknown` | `bounded_unknown` |
| Last observed progress | about 4.686 million conflicts | about 3.866 million conflicts |
| Sampled solver RSS peak | 231,063,552 bytes | 202,883,072 bytes |

The same curve, base, one public target, first raw cofactor preimage, solver,
single thread, and 600-second cap were frozen for Q66 and Q67. Both terminal
conflict counters are null because the solver was externally stopped; the
progress counts above are approximate readings from the retained raw logs.
The conflict difference is a solver-stage observation on an unisolated local
host, not a completed relation or a wall-time speedup. The exact uniform-target
six-subset first moment for the complete base is `C(B,6)/r = 20,831.181431...`;
it is a combinatorial diagnostic, not a measured relation yield for this slice.

The [protocol](protocol.json) binds the source, input, base, solver, and
limits. Its `point_decomposition_summands: 6` describes this experiment;
the inherited `summands: 5` metadata field refers to the five S₃ links in
the six-leaf tree. The [seed receipt](valid_seeds.json) binds the 256-byte
[validity bitset](valid_seed_bits.bin). The [shape](shape.json),
[control](six_point_control.json), and [ordinary result](width11_m6_ordinary.json)
preserve the frozen formula and raw attempts. The 604.244-second
target-dependent PDP interval includes target-preimage construction, formula
build and write, the 599.835-second solver attempt, relation check, and
residual overhead. All timing here is exploratory local CPU timing.

[Independent Sage replay](independent_sage_replay.json) reconstructs all
2,048 seeds in a separate polynomial-field model, checks the validity bitset
and 1,097 subgroup-usable projections, and verifies the planted six-point
group sum. The ordinary row has `no_relation_to_replay` status. The generic
tree-to-six-sum implication is checked in [SixLeafTree.lean](SixLeafTree.lean);
the [Lean output](lean-build.txt) prints no axioms for either theorem. The
specific field, curve, S₃ circuit, and base-policy bridge is checked by the
executed SAT and Sage controls and has not yet been formalized in Lean.

The checked Sage launcher saved [runtime identity](sage_runtime_info.json)
before the workload. From the repository root, reproduce the read-only
receipt audit with:

```sh
python3 experiments/n83-geometric-m6-validseed11-20261012/verify.py
```

The next falsifier should change the decomposition search method on this
same exact base and measure ordinary relation yield and novel rank. Another
600-second SAT slice with different static clauses would add little evidence
about the complete factor-base logarithm pipeline.
