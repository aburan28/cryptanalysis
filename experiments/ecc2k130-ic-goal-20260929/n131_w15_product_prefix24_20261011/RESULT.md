# A 24-bit output-support graph constrains the N131 W15 pair circuit

An exact reduced decision graph now exposes the first **24 reciprocal-output
bits** of each fixed-seed W15 pair to CryptoMiniSat. The first pair has
8,175 allowed prefixes for 8,176 complete outputs; the second has 8,340
prefixes for 8,340 outputs. A full constructed N131 assignment satisfies
all **430,526 CNF clauses and 42,681 native-XOR rows**, and independent
curve-point replay reaches the constructed target. The frozen unpinned
public-point run ends at **`CENSORED_TIME`**, after 598.183 seconds and
509,181,952 bytes sampled combined peak RSS. Its complete formula and raw
solver transcript pass the [archive audit](audit_result.json).

The curve is `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, curve ID
`EC1N131Ckb1heb5f1998f20b`, with subgroup order
`680564733841876926932320129493409985129`. The W15 factor base has
**B=197,292** usable points and **K=16,381** signed-Frobenius columns.
The first two pair XOR seeds are 12004 and 9022 at rotations 0 and 13;
four other pair blocks remain free. Both public formulas use the same
previously published subgroup point
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`.

The [complete archived pair-output roots](../n131_w15_pair_output_prefix_gate_20261010/pair_roots.json)
were enumerated from both admissible source masks, distinct folded columns,
and the exact pair quadratic. [prefix_gate.py](prefix_gate.py) builds a
reduced decision graph over the low 24 bits of each output. At each graph
node, an asserted node requires the branch selected by that output bit;
the asserted root therefore accepts exactly its represented prefix set.
The [projection](projection.json) checks every archived output, counts
every accepting path in the reduced graph, matches that count to the
distinct-prefix set, and probes deterministic absent codes. This is a
necessary support gate on the existing exact pair-product equation: it
does not introduce an alternative source policy.

| Fixed-seed pair | Outputs | 24-bit prefixes | Graph nodes | Forward CNF clauses |
| --- | ---: | ---: | ---: | ---: |
| 12004, rotation 0 | 8,176 | 8,175 | 16,543 | 33,084 |
| 9022, rotation 13 | 8,340 | 8,340 | 16,730 | 33,457 |

For a uniformly distributed 24-bit coordinate, the allowed fractions are
8,175/16,777,216 and 8,340/16,777,216 respectively. This quantifies
the local filter's exact coverage; the distribution of proposed coordinates
inside a target-coupled search requires its own measurement. The earlier
16-bit prefix filter allowed 7,661 and 7,828 signatures, respectively.

| Same public point and source | Product coordinates | Plus 24-bit graph |
| --- | ---: | ---: |
| Variables | 120,940 | 154,213 |
| CNF clauses | 363,985 | 430,526 |
| Native-XOR rows | 42,688 | 42,688 |
| AND gates | 72,641 | 72,641 |
| Terminal status | `CENSORED_TIME` | `CENSORED_TIME` |
| Construction plus search | 598.589 s | 598.183 s |
| Sampled combined peak RSS | 309,051,392 B | 509,181,952 B |

Both gates used one CryptoMiniSat worker, identical solver flags, the
600-second construction-plus-search cap, and the 4-GiB RSS cap. The new
run records 3.263 seconds for formula construction and 592.672 seconds in
the solver; formula compression and receipt work occupy the remaining
parent interval. The [raw log](solver.stdout.txt) records active search,
no final SAT/UNSAT line, and no model line. CPU wall times and conflict
rates on this host are exploratory because host-wide CPU isolation was not
established. The exact graph and circuit changes are structural results;
ordinary relation yield and useful matrix rank remain unknown at this cap.
The complete IC pipeline is still a proposal with `candidate_id: null`.

The [frozen projection protocol](projection_protocol.json),
[public run protocol](run_protocol.json), [checked Sage runtime](sage_runtime_info.json),
[constructed-control receipt](control_result.json),
[public receipt](public_result.json), and [read-only auditor](audit_archive.py)
bind inputs, source hashes, caps, full formula checks, group replay, solver
activity, and terminal status. All local Sage work used this repository's
checked `./sage` launcher.

The next algorithmic gate should constrain **several pair-output families
jointly with the public target** before expanding the four free source
pairs. The 24-bit local graph nearly identifies each fixed pair output,
yet its public search remained censored; another wider local prefix is
unlikely to address the missing multi-pair elimination. An unpinned N41
full-relation control, a source-bound N131 work/RSS projection, and then
independent N131 relation and rank replay are the concrete promotion steps.
