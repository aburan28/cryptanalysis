# Q1453: division-free projective phi5 circuit

Q1453 evaluates the same compact five-input phi invariant as Q1448–Q1452
directly from four sparse raw x coordinates and a fixed public-target raw
x coordinate. It removes the four inverse equations
`u_i * (x_i+1) = 1` from the SAT circuit. The exact N53 and N83 curves,
factor bases, target points, selected preimages, workloads, solver binary,
Gaussian limits, and resource caps are in the [frozen protocol](protocol.json).
N53 uses the known-satisfiable ordinary preimage 201 from Q1452; N83 uses
ordinary preimage 0 from Q1451. This is a `PDP4phi5` stage proposal with
`candidate_id: null` and `isogeny: "none"`.

## Algebraic identity

For five inputs let `d_i=x_i+1`, `u_i=d_i⁻¹`, and `D=∏d_i`. Define
`E=D∑u_i` and `S_j=D² e_j(u_i²+u_i)`, where `e_j` is the elementary
symmetric polynomial. Since `u_i²+u_i=x_i/d_i²`, processing one input
at a time gives exact field recurrences

`D′=D d`, `E′=E d+D`, `S_j′=d² S_j+x S_(j−1)`, and `S_0′=(D′)²`.

The nine terms of the published phi5 invariant, multiplied by `D⁸`, are

`E⁸ + E⁶S₅ + E⁴S₄² + E²S₃²S₅ + S₃⁴ + E²S₅³ + S₂²S₅² + S₅⁴ + D²S₅³`.

The [builder](build_formula.py) uses those recurrences and never expands
ordinary `S5`. In the declared normal basis, field one has weight `n`,
so a leaf with weight at most four or six cannot equal one. The selected
target x is also not one. Thus `D≠0` on every legal input, and the
projective equation is zero exactly when the original phi5 equation is.
The [algebra validation](algebra_validation.json) checks
`F=D⁸ P_phi5` on 64 deterministic random five-tuples at each degree and
on both archived witnesses. The [pinned controls](controls.json) also
solve both Boolean circuits and replay exact four-point group relations.

## Frozen ordinary results

| Field | AND gates, inverse form → projective | CNF clauses, inverse form → projective | Active Gaussian matrices | Last partial conflicts | Solver process | Target-dependent stage | Peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53, known-satisfiable slice | 47,700 → 81,408 | 145,227 → 246,404 | 8 | about 212K | 65.009 s, external timeout | 65.276 s | 190,824,448 bytes | 0 |
| N83, ordinary slice 0 | 117,030 → 199,698 | 355,751 → 603,838 | 5 | 18,375 at last restart | 65.016 s, external timeout | 67.119 s | 220,348,416 bytes | 0 |

The N53 solver child used 52.885 seconds user CPU and 0.898 seconds
system CPU; N83 used 18.980 and 0.412 seconds. These are exploratory
diagnostics on an unisolated host. The last restart counts are partial,
not exact final operation totals. The stage interval includes formula
construction, serialization, solver work, model checks, and blocking;
archive compression is timed separately.

The [archive audit](verification.json) regenerates both exact XCNFs,
checks frozen source hashes, solver settings, compressed inputs, raw
outputs, and all returned models. The protocol recheck covers frozen
input hashes. Both ordinary results are censored. Removing inverse
constraints increased circuit size and did not recover a relation at
either degree under the cap. It provides no natural relation yield,
cost per useful row, N53-to-N83 successful-solve growth rate, or complete
N131 `2^x`. The challenge gate remains closed.

The next algorithm should use a target-conditioned constraint that
processes several sparse leaves or pair outputs together before generic
Boolean branching. Q1453 shows that an equivalent division-free formula
alone does not supply that search rule.
