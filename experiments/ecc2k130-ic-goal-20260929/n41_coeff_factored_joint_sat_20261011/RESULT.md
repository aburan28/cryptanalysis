# Factored coefficients halve the target-coupled quartic circuit

Compiling the 13 `P,Q` coefficients of `A` and eight of `B` from their
exact factorization reduces the complete N41 public-point circuit from
**261,004 to 122,982 AND gates** and from **312 to 159 quartic field
multiplications**. The construction keeps every mask, sign-compatible
output, block branch, and public raw-lift choice free. Its complete
positive assignment passes, five independent bit-field evaluations
match the original universal polynomials, and an independent group
replay reconstructs the same twelve-column public relation.

The paired unpinned query remains `BOUNDED_UNKNOWN` under the frozen
one-worker solver cap. The exact reduction is an implementation result;
the next step is to use the small W6/W15 product spaces inside field
multiplication and target coupling, then retest ordinary relation yield.

## Source and correctness

The [factored compiler](circuit.py) groups the 60-term `A` and 16-term
`B` by powers of the two pair products. It shares monomials in the
seed and output coordinates, shares repeated coefficient factors, and
uses linear squaring for powers of two. It imports the previous
[full circuit](../n41_single_branch_joint_sat_20261011/circuit.py) only
for the unchanged source, column, seed, and public S3 constraints.
The exact coefficient factors come from the checked-Sage
[factorization](../n41_single_branch_joint_sat_20261011/coefficient_result.json).

The [arithmetic replay](arith_replay.json) evaluates the emitted Boolean
coefficient wires on five frozen independent 41-bit input tuples and
compares both outputs with the earlier integer-field evaluator. The
[full assignment](control_result.json) then checks all clauses and
native-XOR rows on the public relation's positive witness. The separate
[raw-curve replay](control_replay_result.json) reconstructs the source
points from masks, checks cofactor-four projection and 12 distinct
folded columns, and sums exactly to the frozen public point.

The curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`; the public point is
`(1458168294740,1672312028033)`, the prime subgroup order is
`549756390943`, and the W6 source has `B=384` usable factor-base
points and `K=26` signed-Frobenius columns. The six rotations remain
`0,5,10,15,20,25`. The [protocol](protocol.json) hashes both circuit
sources, coefficient data, source table, solver, public point, and the
same one-worker, 60-second solver and 4-GiB combined-RSS limits.

| Same N41 public point and exact source | Direct monomials | Factored coefficients |
| --- | ---: | ---: |
| Quartic field-multiplication calls | 312 | **159** |
| Full formula AND gates | 261,004 | **122,982** |
| Variables | 408,089 | **196,018** |
| CNF clauses | 789,713 | **375,647** |
| Native-XOR rows | 146,725 | **72,676** |
| XCNF bytes | 20,045,455 | **9,431,382** |
| Public construction, exploratory seconds | 11.850 | 8.485 |
| Solver interval to parent stop, seconds | 65.254 | 65.090 |
| Combined sampled peak RSS | 348,323,840 B | 198,836,224 B |
| Terminal public-query status | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |

Both solver logs show active search without a SAT or UNSAT terminal
line. The factored log reaches restart row 388 and approximately
116,000 conflicts, while the direct-monomial log reaches row 128 and
approximately 34,000 conflicts. Those counts describe different
formulas and are not a measure of relation-search speed. The
[query receipt](query_result.json) records 8.485 seconds of formula
construction, 0.273 seconds of write and hash, and 65.090 seconds of
solver work, totaling 73.848 seconds. Full compressed
[stdout](solver.stdout.gz) and [stderr](solver.stderr.gz) are retained.
The [terminal audit](terminal_audit.json) rebuilds the identical
9,431,382-byte formula, checks its SHA-256, both logs, phase sum,
positive assignment, and paired source identity. These CPU wall times
are exploratory on a host without an isolation receipt.

## N131 transfer and next experiment

The [arithmetic-width diagnostic](projection_result.json) uses the
same 159 quartic multiplication calls and the measured 5,817 AND gates
for one dense `GF(2^131)` Karatsuba multiplication. The all-dense
kernel estimate falls from 1,814,904 to **924,903 AND gates**. It is
a diagnostic: real operands are structured, and the complete N131
formula, memory, and solver cost have not been measured. The earlier
W15 pair-chain control had 77,021 AND gates. A useful next circuit
must preserve the low-dimensional source-product representation through
the coefficient multiplications, then use the public S3 links to prune
whole product families. The N131 public query remains behind the exact
one-worker, 600-second, 4-GiB promotion gate. The complete IC pipeline
remains `candidate_id: null` pending ordinary N131 relations, useful
rank, factor-base logs, and verified one-target online recovery.
