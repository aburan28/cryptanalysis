# Nondegenerate two-link resultants for the N131 W18 eight-pair circuit

Eliminating three alternating intermediate reciprocal coordinates reduces
the exact W18 eight-pair arithmetic IR from 517,242 to **389,853 live
operations** while retaining the same 33,191-code source table in each slot.
The ordinary public-target XCNF has **479,809 variables, 470,230 CNF
clauses, and 287,038 native XOR rows**. Its constructed relation satisfies
the new equations with nonzero elimination denominators, and an independent
full-formula audit checks every constructed CNF clause and XOR row. The
public-target search reached its frozen one-worker, 615-second parent cap.
Removing the 1,577 constructed-witness pins leaves a known-satisfiable
control, whose independent search also reached its 135-second parent cap.

For two consecutive reciprocal S3 equations sharing middle coordinate `m`,
write `f(m)=(1+h)m²+hm+C` and `g(m)=(1+k)m²+km+Z`, where
`h=(a²+a)(b²+b)`, `k=(c²+c)(d²+d)`, `C=(a+b)²`, and `Z=(c+d)²`.
Set `D=h+k`, `s=kC+hZ`, and `E=C+Z+s`. Then
`(1+k)f+(1+h)g=Dm+E`. In the nondegenerate branch `D≠0`, the common
middle is uniquely `m=E/D`; substituting this value reduces both equations
to the one resultant `E²+Ds=0`. The
[symbolic identity audit](identity_result.json) checks all three polynomial
equalities in characteristic two, with 1,000 deterministic degree-131 field
checks of the S3 quadratic form. The
[circuit control](circuit_result.json) checks `D≠0` for all three blocks on
the frozen constructed relation and recovers each eliminated coordinate.
This experiment explicitly constrains `D≠0` at each block.

The field is `GF(2^131)` under `t^131+t^13+t^2+t+1`, the curve is
`y²+xy=x³+1`, and the prime subgroup order is
`680564733841876926932320129493409985129`. The fixed seed-212 W18
source uses eight Frobenius rotations `0,16,...,112`, with 1,062,112 actual
usable factor-base points before folding and 66,318 folded columns. The
public target is preimage index 0 of workload `cc09e7eb202a`. The
[resultant circuit](resultant_circuit.py) replaces six S3 links with three
five-multiplication blocks, retains one four-multiplication final link, and
keeps reciprocal coordinates after slots 2, 4, and 6. The
[formula builder](build_formula.py) applies the same exact positive-polarity
source BDD as the comparison chain and enforces nonzero `D` in each block.

| Ordinary formula | Four-product S3 chain | Three resultants plus final S3 |
| --- | ---: | ---: |
| Arithmetic IR live operations | 517,242 | **389,853** |
| Variables | 607,585 | **479,809** |
| CNF clauses | 583,402 | **470,230** |
| Native XOR rows | 376,828 | **287,038** |
| Serialized bytes | 20,553,865 | **16,116,753** |

The [comparison build](../n131_w18_positive_bdd_20261010/positive_ordinary_build.json)
and [resultant build](resultant_ordinary_build.json) retain exact source and
target hashes. The constructed [solver receipt](constructed_solver_result.json)
records SAT; the [independent model audit](constructed_audit_result.json)
checks all 471,807 clauses and 287,532 XOR rows and recovers the eight pinned
source pairs and three retained intermediate coordinates. Its solve interval
is a correctness diagnostic on this exploratory host.

The [ordinary protocol](ordinary_solver_protocol.json) freezes one
CryptoMiniSat5 worker, a 600-second solver cap, a 615-second parent cap, and
4 GiB peak RSS. The [ordinary solver receipt](ordinary_solver_result.json)
records `PARENT_TIMEOUT` after 615.101 seconds, with 385,597,440 bytes peak
child RSS. Its last logged restart line has about 1.10 million conflicts.
This is `BOUNDED_UNKNOWN`: no model or unsatisfiability certificate was
produced within the cap. The prepared independent XCNF audit and checked-Sage
group replay apply when an ordinary model is available.

The [pin-removal receipt](unpinned_build_result.json) verifies that only the
1,577 witness unit clauses were removed from the constructed formula. The
remaining 480,303-variable XCNF has 470,230 clauses and 287,532 native XOR
rows; the retained target is the exact constructed raw target. The
[unpinned solver receipt](unpinned_solver_result.json) records
`PARENT_TIMEOUT` after 135.134 seconds with 405,372,928 bytes peak child RSS
and about 172,000 conflicts on the last logged restart line. This control is
known to be satisfiable from the independently audited pinned witness. Its
bounded search shows that reducing arithmetic formula size alone has not
cleared the unpinned search gate on this solver and host. The next algorithmic
step is a stronger source-aware propagation or decomposition method, then an
ordinary-query yield and novel-rank measurement under a frozen protocol.
Factor logs and the paired one-target rho interval follow those gates.
