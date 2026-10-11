# Exact product coordinates reduce the N131 W15 coupled circuit

The two fixed-seed W15 source pairs now use **14 product-coordinate bits per
pair** with exact source-membership decision graphs. This preserves the
admissible unordered source pairs and their possible curve-point sums. In the
complete six-pair N131 circuit, the change removes **60,438 CNF clauses, 167
native-XOR rows, and 262 AND gates** from the prior public-point formula.
The constructed assignment passes all 363,985 CNF clauses and 42,681 XOR
rows, and an independent group lift reaches its recorded target. The frozen
public-point search remained active until `CENSORED_TIME` at 598.589 seconds
under one worker and 4 GiB. The [archive audit](audit_result.json) binds the
public formula, complete control, raw solver log, and terminal receipt.

The exact curve is `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, curve ID
`EC1N131Ckb1heb5f1998f20b`, with subgroup order
`680564733841876926932320129493409985129`. The W15 source has
**B=197,292** usable factor-base points and **K=16,381** folded columns.
The first two pair mask-XOR seeds are 12004 and 9022 at rotations 0 and 13;
the other four pairs remain free. The public subgroup point is
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`. It was fixed before the
search in the [public protocol](public_protocol.json).

For a fixed seed `s`, one source mask `w` and its mate `w+s` have product
`p=w(w+s)=w²+sw`, linear over `F₂`. The product map on W15 has rank 14 and
kernel `{0,s}`. The [preflight](result.json) chooses a zero bit position in
each kernel coset and reconstructs the canonical first mask linearly from
14 product bits; the second is its XOR with `s`. The two original mask
orders produce the same pair-output equation and the same set of group sums
because both leaves use the same Frobenius rotation. Source and folded-column
membership for each canonical pair are enforced by a reduced decision graph.
Every one of the 16,384 product codes in each seed case was checked against
the field product, both masks, source support, folded columns, and graph
evaluation. The 4,088 and 4,170 accepted codes match the prior exact
unordered-pair census. Canonicalization divides its ordered signed-tuple
count by four, to
`5,801,604,789,594,450,782,614,550,456,451,474,695,946,240`; the
point-support set is unchanged by those two pair swaps.

| Exact source component | Seed 12004 | Seed 9022 |
| --- | ---: | ---: |
| Product-image rank | 14 | 14 |
| Admissible unordered pairs | 4,088 | 4,170 |
| Reduced decision-graph nodes | 2,065 | 2,083 |
| Forward source clauses | 4,111 | 4,149 |

| Complete circuit / public gate | Prior two-seed encoding | Product coordinates |
| --- | ---: | ---: |
| Variables | 117,252 | 120,940 |
| CNF clauses | 424,423 | **363,985** |
| Native-XOR rows | 42,855 | **42,688** |
| AND gates | 72,903 | **72,641** |
| Public formula bytes | 24,807,828 | **24,258,904** |
| Public query terminal status | `CENSORED_TIME` | `CENSORED_TIME` |
| Construction plus search | 592.112 s | 598.589 s |
| Sampled combined peak RSS | 685,441,024 B | 309,051,392 B |

Both public runs used one CryptoMiniSat worker, the same point and solver
flags, and a 600-second construction-plus-search cap. The new run recorded
1.649 seconds of formula construction and 595.605 seconds in the solver;
the remaining interval covers formula compression and receipt work. Its
[solver log](solver.stdout.txt) shows active search, no terminal SAT/UNSAT
line, and no model line before the parent wall stop. The prior row and these
CPU wall times are exploratory on a host without an isolation receipt;
neither censored row establishes an online speedup. Ordinary-query relation
yield and useful matrix rank are still unknown for this encoding. The
proposal retains `candidate_id: null` pending a complete pipeline.

The [frozen preflight protocol](protocol.json),
[constructed-control protocol](control_protocol_v2.json),
[checked Sage runtime](sage_runtime_info.json),
[complete control receipt](control_result.json),
[public result](public_result.json), and [read-only auditor](audit_archive.py)
preserve the source, accounting boundary, and validation. The initial
control producer omitted the intentionally reserved circuit wire from its
assignment; [its failure receipt](control_failure_v1.json) is retained, and
the source-pinned second control passes full verification. All new local
Sage work used this repository's checked `./sage` launcher.

The next method gate must use the 14-bit pair coordinates to reject
target-incompatible **multi-pair** families before the remaining four
source pairs are expanded. A complete N41 public-point control and a
source-bound N131 work/RSS projection are needed before another N131 solver
variant. An ordinary N131 relation, novel-rank measurements, factor logs,
fresh-target scalar recovery, and matched one-target rho timing remain the
subsequent pipeline gates.
