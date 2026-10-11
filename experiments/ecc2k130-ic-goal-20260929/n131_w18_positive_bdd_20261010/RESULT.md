# Positive-polarity source BDD for the N131 W18 eight-pair circuit

Propagating truth only from the asserted source BDD root to its selected
children reduces the ordinary eight-pair formula to 607,585 variables,
583,402 CNF clauses, and 376,828 native XOR rows. Relative to the original
XOR/AND source decision gate, that is 203,840 fewer variables, 104,800 fewer
CNF clauses, and 203,888 fewer native XOR rows. The arithmetic IR and exact
factor-base source remain fixed. The constructed model passes an independent
full-formula audit; the frozen public-target search reaches its parent cap.

For each BDD node with selector `s`, low child `a`, high child `b`, and node
literal `v`, [the encoder](positive_bdd.py) emits `v -> (s or a)` and
`v -> (not s or b)`, with terminal constants folded. The asserted root is
true. Along the unique path selected by any selector assignment, these
implications force every visited child true, so a path to the false terminal
is impossible. Conversely, when the BDD accepts, assigning every node its
true Boolean value satisfies the clauses. Thus the projection onto the
selector bits is exactly the [prior exhaustively checked W18 source
BDD](../n131_fixed_seed_eight_pair_circuit_20261010/pair_preflight_result.json).
The local two-clause gate truth table is also checked exhaustively before
each [formula build](build_formula.py). A separate
[native source-projection control](source_projection_result.json) pins accepted
selector code 4 and rejected selector code 0 to the exact BDD gate. The
solver returns SAT and UNSAT respectively under a 20-second per-case cap.

The field is `GF(2^131)` under modulus `t^131+t^13+t^2+t+1`, the curve is
`y^2+xy=x^3+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The fixed W18 source seed 212
has 33,191 valid unordered source pairs per slot. Eight disjoint Frobenius
rotations `0,16,...,112` give 1,062,112 actual usable base points before
folding and 66,318 folded columns. The same public workload `cc09e7eb202a`
and four-product reciprocal S3 arithmetic IR of 517,242 live operations are
used in each formula below.

| Ordinary formula | Original XOR/AND BDD | Direct ITE BDD | Positive-polarity BDD |
| --- | ---: | ---: | ---: |
| Variables | 811,425 | 607,585 | 607,585 |
| CNF clauses | 688,202 | 789,378 | 583,402 |
| Native XOR rows | 580,716 | 376,828 | 376,828 |
| Serialized bytes | 26,716,090 | 24,778,904 | 20,553,865 |

The inputs are the [original W18 build](../n131_reciprocal_s3_fourmul_20261010/fourmul_ordinary_build.json),
[direct ITE build](../n131_w18_direct_ite_bdd_20261010/ite_ordinary_build.json),
and [positive-polarity build](positive_ordinary_build.json). The new
constructed formula's [solver receipt](constructed_solver_result.json)
records SAT, and the [independent model audit](constructed_audit_result.json)
checked all 585,372 clauses and 377,322 native XOR rows while recovering the
eight pinned source pairs and six intermediate reciprocal coordinates.
Constructed solve times on this host are exploratory correctness diagnostics.

The [ordinary protocol](ordinary_solver_protocol.json) freezes one
CryptoMiniSat5 worker, a 600-second solver cap, a 615-second parent cap, and
4 GiB peak RSS on the same public target. The
[ordinary receipt](ordinary_solver_result.json) and
[search log](ordinary_solver.stdout.txt) record `PARENT_TIMEOUT` at
615.143 seconds with 447,758,336 bytes peak child RSS and about 244,000
logged conflicts. The solver did not emit a terminal status before the parent
cap, so the result is `BOUNDED_UNKNOWN`. An ordinary model would require the
prepared independent XCNF audit and checked-Sage curve replay. Candidate
identity and downstream relation yield, rank, factor-log, and same-point rho
fields remain open. The next method gate must change the decomposition search
itself, rather than only shortening this source-membership encoding.
