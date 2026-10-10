# Exact private-XOR projection of the N131 compact public-point formula

The compact ECC2K-130 twelve-atom XCNF now has an exact projected form with
**87,907 variables and 11,150 native-XOR rows**, down from 119,952 variables
and 43,195 XOR rows. It preserves all 333,529 CNF clauses and the exact set
of satisfying assignments on their variables. The [public structural
audit](public/structure_audit.json) remapped every CNF clause and replayed
all 43,195 source XOR equations through 32,045 saved pivots, matching the
11,150 projected XOR rows as a multiset. A complete constructed N131 witness
passed the projected XCNF and reverse-lifted through all 32,038 private
pivots of its corresponding control formula.

The one-worker search on the unpinned published subgroup point reached
`CENSORED_TIME`: 584.344 seconds of active solver work and **590.033 seconds**
for the original target-specific formula construction, projection, and
search together, under the frozen 600-second / 4-GiB gate. Its sampled peak
combined RSS was 1,078,312,960 bytes. The solver log contains active search
but no SAT or UNSAT status line or model. The [terminal audit](terminal_audit.json)
binds the exact original and projected formulas, public point, source and
runtime hashes, controls, caps, and raw logs.

## Projection and certificate

The [protocol](protocol.json) was frozen before projection and search. It
binds the same public point and archived compact XCNF as the
[baseline](../n131_w14_compact_columns_20261010/RESULT.md), with decompressed
SHA-256
`01ff129bda5bc03722bfe97fa4f09b71145ca336a7e2c91779312d9f73446eac`.
The exact curve is `EC1N131Ckb1heb5f1998f20b`; the W14 six-pair geometry
has **B = 98,640** usable projected factor-base points and **K = 8,160**
folded columns. This experiment changes only the point-decomposition solver
representation; the complete IC `candidate_id` remains `null`.

Write the native-XOR system as `A_u u + A_b b = c`, where `b` occurs in CNF
and `u` occurs only in XOR rows. The [projector](../xor_projection_20261009/project_xcnf.py)
eliminates each private pivot by GF(2) row addition and saves its equation.
The residual rows constrain only `b`. The public formula has **zero free
private variables**, so a projected assignment has a unique reverse lift
through the saved equations. The independent [row-replay audit](audit_structure.py)
reduces every original XOR row using those equations and compares the
resulting residual rows with the projected XCNF, while also comparing every
remapped CNF clause. The [constructed witness audit](constructed/control_audit.json)
checks all 333,529 projected CNF clauses and 11,150 projected XOR rows,
reconstructs every eliminated variable, and checks the lifted assignment
against the original constructed formula. It used the
[checked Sage runtime](sage_runtime_info.json).

| Same public target and original Boolean system | Compact source | XOR-projected |
| --- | ---: | ---: |
| Variables | 119,952 | **87,907** |
| CNF clauses | 333,529 | 333,529 |
| Native-XOR rows | 43,195 | **11,150** |
| Native-XOR literal occurrences | 1,394,504 | 3,244,071 |
| Plain XCNF bytes | 18,684,062 | 29,281,335 |
| Formula construction plus projection, seconds | 2.212 | 5.689 |
| Solver wall, seconds | 596.799 | 584.344 |
| Charged construction, projection, and solver, seconds | 599.011 | 590.033 |
| Sampled peak combined RSS, bytes | 676,347,904 | 1,078,312,960 |
| Terminal status | `CENSORED_TIME` | `CENSORED_TIME` |

The [constructed projection](constructed/result.json) removed 32,038
private variables in 2.390 seconds of monitored wall. The
[public projection](public/result.json) removed 32,045 in 3.477 seconds.
Each projected formula, variable map, and ordered reverse-lift file is
archived beside its result. The public projected plain XCNF has SHA-256
`f0be826e9feafe609f20a8e535145d6e8ec6deec6696f3f21b56d28b50fc560d`.
The [solver receipt](public_solver/result.json) records the 584.344-second
parent cap, 522.852 seconds sampled child CPU, zero model lines, and the
raw [solver output](public_solver/solver.stdout.txt). Its last restart
logged approximately 1.298 million conflicts, versus 2.297 million for
the compact source run. Host contention and different search trajectories
make those counts and CPU samples exploratory diagnostics; both wall-time
rows are censored. The projected XOR rows are substantially denser, which
helps explain why fewer variables alone did not produce a completed query.

## Next target-conditioned gate

The exact projection and lift can be reused if a new decomposition circuit
creates private XOR variables. For this W14 six-pair geometry, the next
algorithmic test should instead generate partial-sum outputs from the
*public target constraint* and apply the existing exact four-atom inverse
before expanding source masks. Freeze an unpinned N41 public-point control,
count output proposals and every failed inverse call, and independently
replay an ordinary group relation. A source-bound N131 work/RSS projection
then decides whether to run the 600-second / 4-GiB public-point gate.
