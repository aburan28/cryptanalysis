# Exact W20 seven-pair source gate on the degree-131 challenge curve

Enumerating the full trace-zero W20 polynomial source and all 1,048,575
nonzero pair seeds gives a seven-pair policy with 132,045 valid source pairs
per slot. Its selected factor base has 3,697,260 distinct usable points before
Frobenius folding and 263,959 folded columns. The seven-pair point-decomposition
IR has 450,773 live operations, 66,469 fewer than the W18 eight-pair
four-product chain. Exact source membership, group geometry, and a constructed
XCNF witness are independently checked. The larger W20 source BDD makes the
ordinary formula substantially larger, so its frozen public-target search is
recorded as a separate feasibility gate.

The field is `GF(2^131)` with modulus `t^131+t^13+t^2+t+1`, and the curve is
`y^2+xy=x^3+1`. The prime subgroup order is
`680564733841876926932320129493409985129`. The source uses the W20 span
of `t` through `t^20`, with Frobenius rotations `0,18,36,54,72,90,108`.
The [native census](export_receipt.json) checked all 1,048,575 nonzero masks:
524,493 are rational, 523,999 are folded columns, the full seven-window
union contains 7,342,902 usable points, and reciprocal-Frobenius collision
count is zero. Each table row stores its mask, least Frobenius representative,
and relative Frobenius shift in [support_w20.tsv](support_w20.tsv).

The [all-seed count](count_result_v2.json) uses an integer Walsh–Hadamard
transform and subtracts source pairs within one folded column. Seed 898618
maximizes the accepted pair count. It selects 264,090 rational masks per
window, 263,959 folded columns, and 3,697,260 actual distinct usable points
across seven windows. Four curve-sign choices per accepted pair give 528,180
labeled pair states per slot. Their seventh power divided by `r` is
16.8501676, an upper support ceiling before cross-slot column exclusions and
search completion. The first count run failed only at its final population
count because Python 3.9 lacks `int.bit_count()`;
[its failure receipt](count_run_result.json) and the corrected
[v2 run receipt](count_run_result_v2.json) preserve both attempts.

Fixing the pivot bit of seed 898618 leaves 19 source-selector bits. The exact
source BDD has 44,131 nodes, and [bdd_result.json](bdd_result.json) checks all
524,288 selector assignments against the audited rational mask table. The
checked Sage [group audit](sage_audit_result.json) verifies 24 mask/shift/lift
samples, all 28 sign choices for seven selected source pairs, and all six
reciprocal S3 links on a constructed projected subgroup relation. The
[seven-pair circuit](sevenpair_circuit.py) evaluates all 1,703 field-bit roots
to zero on that relation and rejects the same leaves with the frozen public
target substituted.

| Stage | W18 eight-pair four-product chain | W20 seven-pair four-product chain |
| --- | ---: | ---: |
| Valid source pairs per slot | 33,191 | 132,045 |
| Actual usable base points, before folding | 1,062,112 | 3,697,260 |
| Folded columns | 66,318 | 263,959 |
| Labeled uniform-target support ceiling | 141.831661 | 16.8501676 |
| Source BDD nodes | 13,093 | 44,131 |
| Live point-decomposition IR operations | 517,242 | 450,773 |
| Ordinary XCNF variables | 811,425 | 1,354,163 |
| Ordinary CNF clauses | 688,202 | 1,250,440 |
| Ordinary native XOR rows | 580,716 | 936,218 |

The W20 ordinary formula is fixed to preimage index 0 of the same public
one-target workload `cc09e7eb202a`; its exact hash and phase measurements
are in [sevenpair_ordinary_build.json](sevenpair_ordinary_build.json). The
constructed formula solved in 6.976 seconds on this exploratory host, and
the [independent model audit](constructed_audit_result.json) checked all
1,252,145 CNF clauses and 936,400 native XOR rows, recovering the seven
selected pair masks. That timing is a correctness diagnostic, not a CPU
speedup against the W18 constructed control.

The ordinary solver uses the same CryptoMiniSat5 binary, one worker,
600-second solver cap, 615-second parent cap, and 4 GiB RSS cap as the W18
experiments. Its [protocol](ordinary_solver_protocol.json),
[result receipt](ordinary_solver_result.json), and
[search log](ordinary_solver.stdout.txt) record `PARENT_TIMEOUT` at
615.117 seconds, with 527,745,024 bytes peak child RSS and about 71,000
logged conflicts. The 600-second solver limit did not emit a terminal status
before the 615-second parent cap; this is `BOUNDED_UNKNOWN`, not an
unsatisfiability result. No ordinary model exists to pass the prepared
independent XCNF and Sage group auditors.

The candidate ID remains `null` while ordinary verified relations, relation
yield, rank novelty, factor-log recovery, and matched one-target rho remain
pipeline gates. W20 lowers the arithmetic IR count by 12.9% relative to W18,
but its source BDD has 3.37 times as many nodes, its ordinary XCNF has 1.67
times as many variables, and its labeled support ceiling is 8.42 times
lower. The next focused gate is a smaller exact source-membership encoding on
the same public target and cap, with W18 retained as the stronger current
support reference.
