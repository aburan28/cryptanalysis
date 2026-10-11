# Target-coupled single-branch quartic circuit on the N41 public point

The three-block existential quartic now has a complete **target-coupled
Boolean circuit** for the N41 six-pair source. It links three still-free
four-atom outputs through two reciprocal S3 joins to either reachable raw
lift of the public point. All twelve masks, the four-atom outputs, the
branch variables, and the target-lift choice are unpinned in the query.
The frozen public relation satisfies every one of its 789,713 CNF
clauses and 146,725 native-XOR rows, and a separate integer-field group
replay reconstructs its twelve raw leaves and exact public sum.

The first unpinned one-worker search is `BOUNDED_UNKNOWN`: it remained
active through the 65-second parent solver stop without a SAT or UNSAT
line. This exact result directs the next circuit change toward arithmetic
width reduction before the N131 public query.

## Construction and exact controls

The curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, with
prime subgroup order `549756390943`, public point
`(1458168294740,1672312028033)`, actual factor base `B=384`, and
26 signed-Frobenius columns. The source uses W6 masks at rotations
`0,5,10,15,20,25`. The final four pairs form two same-seed blocks;
their seeds differ by an offset in `0..7`. The [circuit](circuit.py)
enforces source admissibility, twelve distinct folded columns, pair
ordering, both seed equalities, the offset, one Artin--Schreier and
one quartic equation per four-atom block, and the two public-target
joins. The raw target lift is a free Boolean choice between corrected
indices 0 and 1.

The [protocol](protocol.json) fixes the source and producer hashes,
the public target, one worker, a 120-second construction cap, a
60-second solver cap with a five-second parent margin, and 4 GiB
combined RSS. The [control receipt](control_result.json) checks the
complete XCNF assignment from the independently verified relation.
The [group replay](control_replay_result.json) independently rebuilds
source points from each mask, checks their cofactor-four projections
against the frozen source table, enumerates the rational sign choices,
and finds exactly one twelve-column lift of the public point. Each of
the three block reciprocal outputs admitted two rational sign choices
before the final target and intermediate-point checks.

| N41 public circuit stage | Recorded value |
| --- | ---: |
| Quartic field-multiplication calls / linear squares | 312 / 138 |
| Variables / AND gates | 408,089 / 261,004 |
| CNF clauses / native-XOR rows | 789,713 / 146,725 |
| Target-dependent construction | 11.850 s |
| Formula write and hash | 0.330 s |
| Solver interval to parent stop | 65.254 s |
| Construction through stop | 77.435 s |
| Formula bytes / SHA-256 | 20,045,455 / `b3a15755f968ca142a4dc8a6a0e646943e92eb899bdef56310fe9596253ed51e` |
| Sampled combined peak RSS | 348,323,840 B |
| Search status | `BOUNDED_UNKNOWN` |

The [query receipt](query_result.json) preserves exclusive phase
intervals, exact resource stop, formula hash, and solver exit state.
The compressed [stdout](solver.stdout.gz) and [stderr](solver.stderr.gz)
are retained byte for byte. Stdout shows active restarts through row 128
and approximately 34,000 conflicts; the parent killed the process at
its predeclared margin after CryptoMiniSat's 60-second flag had not
returned a terminal line. The [terminal audit](terminal_audit.json)
rebuilds the identical formula, checks both logs and the phase sum,
and verifies the positive control and independent group replay. The
host had no CPU-isolation receipt, so these wall times are stage
diagnostics.

## Arithmetic-width experiment and N131 gate

Exact Sage factorization finds the universal 60-term `A` and 16-term
`B` irreducible and coprime over `GF(2)[a,S,Z,P,Q]`
([record](factor_result.json)). Grouping by `P,Q` yields 13 coefficient
polynomials for `A` and eight for `B`; several of those coefficients
factor into much smaller forms ([record](coefficient_result.json)).
This supplies a concrete next implementation: compile and share those
coefficient factors before emitting the target-coupled formula, then
measure the full N41 public query on the same point and resource cap.

The checked Sage launcher saved its [runtime receipt](sage_runtime_info.json).
An initial coefficient-factor invocation stopped during Sage import
because the repository volume had only 32 MiB free; its
[infrastructure failure](infrastructure_failure.json) is separate from
the later successful exact factorization.

The [N131 transfer diagnostic](projection_result.json) retains the
same emitter's 312 quartic multiplication calls and measures one
independent dense Karatsuba field multiplication at 5,817 AND gates
for `GF(2^131)`. If all 312 calls had two dense operands, that part
alone would emit 1,814,904 AND gates, versus 77,021 AND gates in the
previous complete N131 W15 pair-chain control. Operand structure can
change the emitted count; this is an arithmetic-width diagnostic,
not a full N131 formula measurement or time bound. The N41 query's
censored result and the unmeasured complete N131 circuit leave the
one-worker, 600-second, 4-GiB promotion gate unestablished. The
complete IC pipeline remains `candidate_id: null` while the joint
search, useful relation rank, factor-base logs, and fresh single-target
online comparison are developed.
