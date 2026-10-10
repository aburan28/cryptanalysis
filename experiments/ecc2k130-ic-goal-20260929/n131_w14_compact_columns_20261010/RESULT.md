# Exact compact column constraints for the N131 coupled six-pair formula

The folded-column distinctness condition in the twelve-atom ECC2K-130
formula now uses **8,250 clauses** instead of **550,704**, while preserving
the same set of allowed source-mask assignments. The complete public-point
XCNF shrank from **875,983 to 333,529 CNF clauses**. A full constructed
assignment passed all 333,529 clauses and 43,188 native-XOR rows. The
unpinned published-point search used the frozen 600-second / 4-GiB gate and
recorded `CENSORED_TIME` after 599.011 seconds of formula construction plus
search, with no SAT or UNSAT line. The [terminal audit](terminal_audit.json)
checks the source hashes, formula streams, solver activity, resource bounds,
and retained capped outcome.

## Exact equivalence of the column condition

All twelve slots use the same audited map from 8,220 valid W14 masks to
8,160 signed-Frobenius columns. The map has 8,102 singleton columns, 56
columns with two masks, and two columns with three masks. For two slots,
equal columns occur in exactly two cases: their masks are identical, or
they are *distinct masks in the same column*. Fourteen XOR comparisons and
one OR clause rule out identical masks. Only the **124 ordered distinct
alias pairs** need explicit forbids. There are 66 slot pairs, giving
`66 + 66*124 = 8,250` column clauses. The old encoding listed all
same-column mask pairs, including the 8,220 equal-mask cases, separately
for every slot pair. The [exhaustive predicate check](column_equivalence.json)
compared the old and compact conditions on all **67,568,400 ordered pairs**
of valid masks and found exact agreement.

The [compact circuit](circuit.py) leaves the six diagonal pair equations,
two shared seed equalities, four upper reciprocal joins, target-linear join,
valid-mask constraints, and target-fiber alternatives unchanged. It requests
924 bit comparisons; common-subexpression sharing makes the public formula's
net native-XOR increase 910 rows. The [frozen protocol](protocol.json) binds
the same published ECC2K-130 subgroup point, one worker, solver flags,
600-second construction-plus-search cap, and 4-GiB combined RSS limit as
the [baseline coupled formula](../n131_w14_coupled_sixpair_sat_20261010/RESULT.md).
The actual projected base remains **B = 98,640** points and **K = 8,160**
folded columns. The experiment is a formula-stage method variant, with
`candidate_id: null` until ordinary public relations and downstream stages
are established.

| Exact public formula | Baseline | Compact columns |
| --- | ---: | ---: |
| Variables | 119,042 | 119,952 |
| CNF clauses | 875,983 | **333,529** |
| Column-distinctness clauses | 550,704 | **8,250** |
| Native-XOR rows | 42,285 | 43,195 |
| AND gates | 75,275 | 75,275 |
| Decompressed formula bytes | 78,316,508 | 18,684,062 |

The [constructed-control receipt](control_result.json) records exact
assignment checks over the complete compact XCNF. Its 119,945 variables,
333,529 clauses, and 43,188 XOR rows differ slightly from the public
formula because the latter uses four unpinned target-preimage choices.
The source curve, twelve raw control points, intermediate sums, and
cofactor-four projection had already passed an independent checked-Sage
replay in the baseline study; this run tested the revised Boolean encoding
against that same witness. The checked Sage build used for construction is
recorded in [sage_runtime_info.json](sage_runtime_info.json).

## Bounded public query

The [public receipt](public_query/result.json) records 2.212 seconds for
formula construction and 596.799 seconds of active CryptoMiniSat search,
for 599.011 seconds charged to the frozen query cap. Archive and receipt
writing brought total process wall to 601.753 seconds. Combined sampled
peak RSS was 676,347,904 bytes. The solver exited after the parent applied
its wall cap; its [raw stdout](public_query/solver.stdout.txt) has active
restart progress and no terminal SAT or UNSAT line. The archived
[public XCNF](public_query/system.xcnf.gz) decompresses to SHA-256
`01ff129bda5bc03722bfe97fa4f09b71145ca336a7e2c91779312d9f73446eac`.
The baseline also ended with `CENSORED_TIME` under the same wall and memory
limits. Both public-point rows retain zero verified relations and zero useful
rank under those caps.

The last logged restart showed approximately 2.297 million conflicts for
the compact formula versus 652 thousand for the earlier formula, while
sampled solver CPU time was 434.8 versus 236.3 seconds. These are
exploratory search diagnostics from an unisolated, differently contended
host, not a controlled wall-time speedup. CryptoMiniSat's log reports that
it enabled **zero Gaussian matrices** from the large XOR components in this
run. The next bounded solver experiment should keep this exact compact
formula and public point but admit the five moderate 2,747–3,315-row XOR
components with explicit matrix-size flags. It must first verify actual
matrix use and retain every capped outcome; an independently replayed group
relation is still the gate for moving toward the N131 factor-log system.
