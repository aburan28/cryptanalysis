# Target-independent W15 prefix with five unrestricted pairs

Fixing two W15 factor-base columns before the target is supplied leaves ten
source atoms in five unrestricted pairs and reduces the published-point
Boolean system to **97,074 variables, 354,246 CNF clauses, and 34,509
native-XOR rows**. Compared with the preceding W15 six-pair circuit, that is
20.297% fewer variables, 18.886% fewer clauses, and 20.264% fewer XOR rows.
The [constructed control](control.json) passes a complete XCNF assignment
check and recovers its twelve-atom group sum. The [frozen public query](result.json)
reached `CENSORED_TIME` after **592.101 seconds** of target formula
construction and CryptoMiniSat search with one worker and a 4-GiB cap.
Its sampled peak combined RSS was **796,459,008 bytes**. The
[terminal audit](terminal_audit.json) verifies the formula, trace clauses,
solver activity, source hashes, and resource receipt; the
[archive check](archive_receipt.json) verifies those bytes after promotion
into this directory.

## Exact source geometry

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The inherited W15
source has 16,441 rational nonzero masks, 197,292 distinct subgroup-usable
factor-base points before orbit folding, and 16,381 signed-Frobenius
columns. The prefix uses masks `4` and `17`, selected as the first two
increasing W15 masks with distinct folded columns outside the archived
constructed residual control. This rule is independent of the published
target. The checked-Sage [prefix audit](prefix_sage_audit.json) independently
replays both source points, their cofactor-four projections, the group sum,
and both residual targets.

For a uniform subgroup target, the source has exactly
**45,910,670,045,280,721,008,901,187,314,530,927,830,630,400** signed
unordered five-pair tuples with all twelve folded columns distinct. Dividing
by the subgroup order gives **67,459.6666008669** tuples per uniform target
before excluding zero intermediate points. This is an exact source-density
calculation, rather than a measured relation rate. After the two fixed
columns, the remaining column multiplicities are 16,323 of size one, 55 of
size two, and one of size three. Thus the tuple count is
`2^5 * 10! * [x^10] (1+x)^16323 (1+2x)^55 (1+3x)`.
The [primary count](support_count.json) and
[independent binomial replay](support_audit.json) agree on the integer and
bind the W15 source table by SHA-256. Before the cross-column filter, the
five-pair group-wide mean is 67,831.2396656.

## Public gate and accounting

| Exact published-point query | Prior W15 six-pair circuit | Fixed prefix, five unrestricted pairs |
| --- | ---: | ---: |
| Variables | 121,794 | **97,074** |
| CNF clauses | 436,725 | **354,246** |
| Native-XOR rows | 43,279 | **34,509** |
| Target formula plus solver, seconds | 590.073 | 592.101 |
| Sampled peak combined RSS, bytes | 691,568,640 | 796,459,008 |
| Public query status | `CENSORED_TIME` | `CENSORED_TIME` |

The [v2 protocol](protocol.json) fixes the published subgroup point, the
target-independent prefix, one solver worker, a 600-second
construction-plus-search cap, 4-GiB combined RSS cap, source and solver
hashes, and CryptoMiniSat flags. Its public residual point is
`(2067351684528269255999060725659477718367,
375444029458909908853403041471845582417)`. Target-dependent timing starts
at subtraction of the prefix sum and includes 2.228 seconds of formula
construction and 589.873 seconds of solver search. The raw
[solver log](solver.stdout.txt) records active restarts and no terminal SAT
or UNSAT line or model before the solver-wall cap. The public
[compressed XCNF](system.xcnf.gz) expands to 21,608,680 bytes with SHA-256
`ea1db85a5506725a014119b7a471c245a6646ed4d77bbd96dd8f35f5bd287afb`.
The preceding and current timings are diagnostics on an unisolated host;
both rows are censored and do not give time-to-relation measurements.

The first v1 launch stopped at a producer assertion before starting the
solver. That assertion incorrectly required the public formula to have the
same variable and XOR-row counts as the constructed control. The public
formula has one fewer of each, while its CNF clause count is the same. The
[failure receipt](failure_v1.json), [archived v1 XCNF](failure_v1.xcnf.gz),
and [archive binding](failure_v1_archive.json) preserve that outcome. V2
removed the invalid equality and retained the control assignment check,
target trace restrictions, CNF count check, source freeze, and full
terminal audit. The v1 and v2 public formulas have the same SHA-256.

The complete IC `candidate_id` remains `null` until an ordinary relation,
useful matrix rank, factor-base logs, and a verified single-target recovery
have been measured. The next algorithmic gate is a target-conditioned
partial-sum generator that leaves at least four pair blocks free and rejects
unrealizable families before mask expansion. First run it on an unpinned
ordinary N41 query, recording verified relations, novel rows per query,
all failed attempts, and charged costs. Advance to the N131 public point
only after a source-bound work and memory projection fits the frozen
600-second, 4-GiB gate.
