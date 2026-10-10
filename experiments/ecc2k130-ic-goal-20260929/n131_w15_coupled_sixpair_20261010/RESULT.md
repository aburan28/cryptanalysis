# Exact W15 six-pair geometry and bounded ECC2K-130 public query

Extending each polynomial source space from W14 to **W15** gives the same
six-pair method **197,292 distinct subgroup-usable factor-base points** and
**16,381 signed-Frobenius columns** on the exact degree-131 challenge curve.
The exact seed-sum count rises to **34,156.259 six-pair tuples per subgroup
point on average** before cross-pair column exclusions, **1,024.948 times**
the W14 count at that same boundary. The complete W15 constructed assignment
passed 436,725 CNF clauses and 43,272 native-XOR rows; its twelve curve
atoms were also recovered by the new W15 group lift.

The unpinned published-point query entered CryptoMiniSat search under a
frozen one-worker, 600-second, 4-GiB gate. It recorded `CENSORED_TIME` after
**590.073 seconds** of target formula construction plus search, with
**691,568,640 bytes** sampled peak combined RSS. The
[terminal audit](terminal_audit.json) checked the exact curve, public point,
source and solver hashes, formula, resource bounds, and raw solver activity;
the [archive receipt](archive_receipt.json) binds the compressed XCNF and
logs copied byte for byte into [public_query](public_query). The solver
logged no SAT or UNSAT line or model. This measured gate shows that the
extra tuple density alone does not clear the current Boolean search barrier.

## Exact source and factor-base geometry

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)`, and the curve is
`y²+xy=x³+1`, with curve ID `EC1N131Ckb1heb5f1998f20b`. The six
same-rotation source-pair blocks use Frobenius rotations
`0,13,26,39,52,65`; each source is the span of `t,...,t^15`. The exact
native [support census](support_receipt.json) found **16,441 rational
nonzero masks** among all 32,767 masks. Its six rotated source spaces have
pairwise rank 30 and no subgroup-usable point overlap. The independent
[Sage mask/orbit audit](sage_support_audit.json) checked every mask,
source Frobenius alias, reciprocal overlap, and rotated-space rank. The
[Sage group audit](sage_group_audit.json) reconstructed every cofactor-four
projected x-coordinate and checked the group law and subgroup membership
on independently lifted points. The [support protocol](support_protocol.json)
was frozen before the measured native run, and the
[checked Sage runtime](sage_runtime_info.json) was saved before the audits.

For one source pair, the [Walsh XOR autocorrelation
count](seed_sum_count.json) includes only rational masks from distinct
folded columns and both signs. It gives 540,579,832 signed pair states per
rotation and 8,918,874,017,088 same-seed two-pair states. With two
four-atom seed equalities, the exact tuple count divided by the prime
subgroup order is the group-wide mean above. That count has not applied
distinct-column exclusions *between* different pairs; it is an upper bound
for the mean number of row-valid tuples under a uniformly selected target.
It is a source-density screen, separate from measured relation yield.

| Same curve, six pairs, and public point | W14 compact | W15 |
| --- | ---: | ---: |
| Rational source masks | 8,220 | **16,441** |
| Actual factor-base points `B` | 98,640 | **197,292** |
| Folded columns `K` | 8,160 | **16,381** |
| Group-wide tuple mean before cross-pair column checks | 33.325 | **34,156.259** |
| Public XCNF variables | 119,952 | 121,794 |
| Public CNF clauses | 333,529 | 436,725 |
| Public native-XOR rows | 43,195 | 43,279 |
| Construction plus solver wall, seconds | 599.011 | 590.073 |
| Sampled peak combined RSS, bytes | 676,347,904 | 691,568,640 |
| Public query status | `CENSORED_TIME` | `CENSORED_TIME` |

## Circuit, public run, and accounting

The [W15 circuit](w15_circuit.py) retains the six diagonal-pair equations,
two shared seed-sum equalities, four upper S3 joins, target join, and exact
folded-column exclusions of W14. It adds one source bit to each of twelve
atoms and expands the product space from 27 to 29 bits. The
[frozen circuit protocol](protocol.json) binds the W15 support, solver,
original control, target point, and source hashes. The
[constructed-control receipt](control_result.json) records a complete
XCNF assignment check, and the [group-lift receipt](control_group_lift.json)
reproduces the twelve raw points and their exact sum.

The [public query protocol](query_protocol.json) fixes the same published
point as W14, one worker, 600 seconds for target-specific formula
construction plus solver work, and 4 GiB combined RSS. The first launch
ended before formula construction when the repository volume returned
`ENOSPC` creating the output directory. The frozen
[temporary-volume runner](query_temp.py) then put large transient files on
the separate local `/private/tmp` volume; the measured public run began
from a new frozen protocol and is fully retained in the repository archive.
Its [result](public_query/result.json) records 2.924 seconds of target
formula construction and 587.150 seconds of solver work. Archive writing
followed the charged interval. The public formula decompressed to
25,757,446 bytes with SHA-256
`aa131adfdd32513e8d24405b2a2ed2698e643447e49aa68201db0eb0820525b8`.
The raw [solver log](public_query/solver.stdout.txt) has active restarts,
ending near 2.480 million conflicts. The W14 and W15 searches used
different solver-wall reservations within their 600-second gates and ran
on an unisolated host; conflict and CPU differences are exploratory.
Neither censored row supplies a time-to-relation or one-target speedup.

The complete IC `candidate_id` remains `null` pending ordinary public
relations, useful matrix rank, factor-base logs, and fresh target recovery.
The next algorithmic gate is a target-conditioned generator of partial-sum
outputs for the exact four-atom inverse, carrying multiple free blocks and
rejecting families before mask expansion. Test its ordinary relation and
rank behavior on an unpinned N41 point, then use a source-bound N131 work
and memory projection before another frozen challenge-width query.
