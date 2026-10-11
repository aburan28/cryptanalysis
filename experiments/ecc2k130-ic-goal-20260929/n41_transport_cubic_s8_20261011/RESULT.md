# Transported N41 eight-slot cubic circuit and pair-order control

The `1+π` source transport gives the eight-slot N41 public point an exact
halftrace-cubic decomposition circuit with **7,507 AND gates**. A complete
eight-point assignment passes all 23,249 clauses and 4,744 native XOR rows.
Canonical ordering inside the four same-rotation source pairs removes a
factor of `2^4=16` from the valid mask-witness space while preserving every
group decomposition. Its complete assignment passes the strengthened circuit;
the original noncanonical assignment is rejected. The two unpinned
public-point searches both ended `BOUNDED_UNKNOWN` at the frozen parent cap.

## Exact instance and construction

The field is `GF(2)[t]/(t^41+t^3+1)` and the curve is
`y^2+xy=x^3+1`, with odd subgroup order `549756390943`. The public point
is `Q=(1458168294740,1672312028033)`; the solver input is
`T(Q)=(920359962848,755404565011)` for `T=1+Frobenius`.
The source uses `W6=span(t,...,t^6)` at rotations
`(0,0,10,10,20,20,30,30)`. The [source census](../n131_w18_four_pairs/screen.json)
has 64 distinct usable projected points per rotation and disjoint
rotation windows, giving actual `B=256`; the signed/Frobenius quotient has
`K=26` columns. The exact source mask set has 32 rational masks per window.

For each raw source point `P`, set `D=P+π(P)`; its reciprocal
coordinate is the rotated sparse seed `w=1/x(D)`. The checked-Sage
[fixture producer](prepare_sage.py) replays the prior public relation,
constructs all eight `D` points, verifies
`[4]sum(D_i)=T(Q)`, and records four raw preimages of `T(Q)`.
Their reciprocal coordinates have a nonzero two-flag cross term
`661152386556`, so the [circuit](circuit.py) uses the exact two-bit
multiplexer with one flag-product gate. On the odd subgroup,
`(1+π)(−π)=[2]`, making the target transport injective and invertible.

Each source pair and each higher binary-tree link uses the exact
halftrace-cubic equation, its trace condition, and a branch bit. A BDD
enforces rational seed membership. All eight masks and their folded
columns are distinct. The [ordered variant](ordered.py) adds 1,984
forbidden mask pairs so that the numeric left mask is smaller than the
right mask in each of the four same-rotation pairs. Pair addition is
commutative; swapping the two sources preserves the pair output and every
column check, proving that one ordered representative exists in each
16-member mask orbit.

## Frozen public-query measurements

Both runs used one CryptoMiniSat worker, `--xor=0`, `--random=20261011`,
`--maxtime=600`, 4 GiB combined RSS, and a 615-second parent stop.
The input point and curve are identical; only the pair-order clauses change.
The stage times below are exploratory local wall times. The public query
starts after target transport, base preparation, and source fixture loading.

| Variant | Clauses | AND gates | Native XOR rows | Formula bytes | Solver seconds | Total seconds | Peak combined RSS | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Cubic source | 23,249 | 7,507 | 4,744 | 625,967 | 615.207 | 615.307 | 174,014,464 B | `BOUNDED_UNKNOWN` |
| Cubic + pair order | 25,233 | 7,507 | 4,744 | 708,799 | 615.121 | 615.261 | 200,114,176 B | `BOUNDED_UNKNOWN` |

The exclusive phases in the [base query receipt](query_result.json) are
0.083912 s construction, 0.001294 s formula write/hash, 615.206630 s
solver, and 0.015342 s post-solver log capture. The corresponding
[ordered receipt](ordered/query_result.json) records 0.127023 s,
0.001793 s, 615.120874 s, and 0.011763 s. The [base audit](terminal_audit.json)
and [ordered audit](ordered/terminal_audit.json) rebuilt their exact formula
hashes, checked frozen source hashes and compressed solver logs, and reconciled
the phase sums. The known-assignment checks are
[base](control_result.json) and [ordered](ordered/control_result.json).

The first frozen [protocol](protocol.json) wrote `factor_base_B: 128` by
counting only one of the two curve signs. Its immutable audit records the
corrected actual count `B=256` from the four 64-point windows; the formula
and query inputs are unaffected. The [ordered protocol](ordered/protocol.json)
uses `B=256` directly. Both remain design proposals with `candidate_id: null`.

## Method decision

Pair ordering is an exact, cheap symmetry reduction but did not resolve
this SAT query within the cap. The next algorithmic test should constrain
*families of partial sums* with the public target before completing all
eight source masks: expose a pair-output prefix jointly with a middle-sum
prefix, derive a sound target-conditioned rejection rule, and measure its
rejection count and cost on the same N41 point. A positive N41 control
would precede any N131 promotion under its four-GiB/600-second gate.
