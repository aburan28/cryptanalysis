# Exact one-hot source membership for the N131 W18 eight-point circuit

Splitting each 18-bit W18 source mask into two nine-bit selectors reduces the
complete public-point formula from **288,232 to 73,744 AND gates** and from
**30,701,742 to 10,610,640 XCNF bytes**. This is an exact change to the
source-membership gate on the same curve, base, eight-slot decomposition tree,
and public target. The complete 262,144-mask lookup table and a constructed
eight-point assignment pass independent replay.

## Method and exactness

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is the
audited `W18=span(t,...,t^18)` table of 131,307 rational masks. Its eight
slots use rotations `(0,0,32,32,64,64,96,96)`, with actual factor-base size
`B=1,050,456` and folded column count `K=131,068`. The frozen one-target
workload `cc09e7eb202a` supplies the same public point as the preceding
[trace-pruned cubic circuit](../n131_w18_cubic_correct_trace_20261011/RESULT.md).

For mask `m=(h,l)` with nine-bit halves, let `H_i(h)` and `L_j(l)` be
one-hot equality indicators. If `S_i` is the set of valid low halves for
high half `i`, the membership bit is

`F(m) = XOR_i [H_i(h) AND (XOR_{j in S_i} L_j(l))]`.

Exactly one `H_i` and one `L_j` are true for every input. Thus `F(m)=1`
exactly for a mask in the frozen source table. Grouping the low-half row
parities in six-selector blocks shares repeated XOR subexpressions. The
remaining pair-product, cubic-link, target-preimage, and folded-column
constraints are built by the same frozen trace-circuit source. The
[protocol](protocol.json) binds the table and implementation hashes before
measurement; the [solver protocol](solver_protocol.json) additionally binds
the exact public formula hash, solver, limits, and flags.

Each nine-bit selector bank costs 1,020 AND gates after its one-bit level.
All 512 high-half rows are nonempty, so their final conjunctions cost 512
more. This gives exactly 2,552 source-membership AND gates per mask and
20,416 across eight slots. It accounts for the measured gate reduction
without using SAT timing as a proxy for it.

| Full public formula, same target | Previous BDD | Nine-plus-nine one-hot | Ratio, previous/new |
| --- | ---: | ---: | ---: |
| Source-membership AND gates | 234,904 | **20,416** | 11.51 |
| All AND gates | 288,232 | **73,744** | 3.91 |
| Variables | 808,085 | **154,709** | 5.22 |
| CNF clauses | 879,270 | **235,806** | 3.73 |
| Native-XOR rows | 518,915 | **80,027** | 6.48 |
| XCNF bytes | 30,701,742 | **10,610,640** | 2.89 |

The prior values are from the frozen public-query receipt. The [new formula
receipt](result.json) records SHA-256
`2571ba0af9b19d711e4735709ff6ac0bff04eeccaafe8c517854ef86f05decc5`
and exploratory construction/write times of 9.202/0.073 seconds on this
unisolated host. The non-source AND counts match the previous circuit:
1,296 source-product, 20,415 first-link, and 31,617 joint-link gates.
The source-table and trace-circuit SHA-256 values in both pre-run protocols
agree, so the formula comparison uses the same frozen inputs and downstream
circuit source.

The [independent audit](audit.json) compared every 18-bit input against the
original table, exercised 32 accepted and 32 rejected masks in the Boolean
circuit, and replayed a full constructed eight-point witness through all
228,210 clauses and 79,641 XOR rows of its one-target control formula. That
control uses its separately recorded constructed point; the public formula
above uses the frozen ordinary point.

The public solver attempt used one CryptoMiniSat worker, a 600-second solver
cap, a 615-second parent cap, and a 4 GiB combined RSS cap. It recorded
**`BOUNDED_UNKNOWN`** after 615.103 seconds in the solver process, with
215,891,968 bytes peak sampled parent-plus-solver RSS and no memory-cap hit.
The exclusive exploratory phases were 14.908 seconds formula construction,
0.295 seconds write/hash, 615.103 seconds solver process, and 0.010 seconds
post-solver log capture, totaling 630.317 seconds. The [solver receipt](solver_result.json)
binds the formula, command, compressed logs, return code, and phase sum. The
[terminal audit](terminal_audit.json) confirms XCNF parsing and active search
before the parent wall stop. The solver run rebuilt the byte-identical formula;
its construction interval differs from the earlier formula receipt on this
unisolated host. The preceding BDD run on this same public point
also recorded `BOUNDED_UNKNOWN` under its matched solver and memory caps.
These CPU intervals are diagnostics from an unisolated host, not a measured
single-target online speedup.

The method is a component proposal with `candidate_id: null`. The exact
source-gate reduction frees substantial circuit budget, but the bounded
ordinary query keeps the next solver gate concrete: constrain at least two
unresolved pair-output families jointly from the public point before
expanding all eight source masks. A candidate can advance to relation-yield
and rank measurement once such a query returns independently replayed
ordinary decompositions under a frozen budget.

To reproduce the source and formula measurements, run
`python3.12 -B experiments/ecc2k130-ic-goal-20260929/n131_w18_onehot_source_20261011/measure.py measure`
and then the sibling `audit.py` from the repository root. The solver is
launched by `solve.py run` using its previously frozen protocol.
