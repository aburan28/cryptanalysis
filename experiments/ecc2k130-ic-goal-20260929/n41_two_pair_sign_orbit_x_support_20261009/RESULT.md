# Exact x-coordinate inverse for the frozen N41 two-pair completion domain

**The 3,167,136 valid two-pair completion assignments form 1,583,568
negation pairs, and each pair has a distinct group-sum x coordinate.** Thus
an N41 residual has an exact two-free-pair completion precisely when its
x coordinate belongs to this 1,583,568-element support. On support, the
x coordinate also determines both pair seed sums and all four folded
columns; the residual y coordinate selects one of the two global signs.
The [independent checked-Sage audit](audit.json) verifies the sign map on
all 256 source points and 7,824 single-pair states and recounts every
valid two-pair assignment. The distinct-x conclusion combines this map
with the earlier [full independent group-sum census](../n41_two_free_pair_occupancy_20261009/audit.json).

## Exact statement and proof

Let `D2,D3` be the frozen last-two-pair domains on
`EC1N41Ckb1h7d5e80d3c4d0`. Each has 1,956 signed, distinct-column
two-point states. Let `A` contain the ordered pairs `(u,v)∈D2×D3` whose
four folded columns are distinct, and let `S={u+v:(u,v)∈A}`. The prior
audited census establishes `|A|=|S|=3,167,136`: the sum map is injective
on this exact domain.

Every one of the 64 points in each source window has exactly one negative
source point with the same seed mask and folded column. Consequently each
single-pair state has a unique negative state, with the same seed-sum mask
and two-column set. Negating both pair states gives a fixed-point-free
involution on `A`; it preserves the four-column condition and sends the
group sum to its negative. The [producer](result.json) and Sage audit count
exactly 1,583,568 two-element assignment orbits, distributed over all
`63²=3,969` nonzero seed-sum pairs. Each seed-sum bin has 128–832 orbits.

The prime subgroup has odd order. If a valid assignment summed to the
identity, its distinct negated assignment would have the same sum,
contradicting the independently audited injectivity. Every sum therefore
has nonzero x. On `y²+xy=x³+1`, a nonzero x has at most two curve points,
`P` and `-P`; the involution supplies both. Injectivity ensures that two
different assignment orbits cannot share an x. Hence `|x(S)|=1,583,568`,
and for every nonidentity subgroup residual `R`,

`R ∈ S  ⇔  x(R) ∈ x(S)`.

The identity is outside `S` and is rejected separately. Each supported x
has a unique assignment orbit; both members preserve the pair seed sums
and folded columns. This is an existence theorem for an exact x-to-pair
inverse on the frozen support, not yet a compact evaluation algorithm.

## Frozen execution and algorithmic consequence

The [protocol](protocol.json) hashes the exact geometry, source arithmetic,
prior producer and Sage audit, and both new sources before execution. The
pure-Python producer took 0.862 s and peaked at 22,560,768 bytes. The
independent Sage audit took 1.810 s inside the checked runtime and peaked
at 267,059,200 bytes; its [runtime receipt](sage_runtime_info.json) was
saved before the job. Both executions stayed within the frozen 120-second,
4-GiB diagnostic caps. Their wall times are exploratory on an unisolated
host, and are certificate costs rather than relation-search timings.

The earlier public-target census counted 19 prefix residuals in `S`, of
which 12 completed an eight-column relation. The exact x predicate has
the same 19 hits: each supported x includes both signs with identical
suffix columns. A proposed extra y-coordinate feasibility test cannot
reject more residuals for this sign-closed domain, although y may still
make an equivalent algebraic test cheaper or select the decoded sign.
The next constructive experiment should derive a compact, target-evaluated
inverse or exclusion rule for x and the pair seed sums, then test it while
multiple pair blocks remain free. Its N131 work and memory must be derived
from that exact representation; the N41 x table itself is not an N131
resource projection. In particular, the x-only mixed-cubic family has
already been [ruled out by full rank](../n41_two_pair_cubic_seed_coordinate_20261009/RESULT.md),
so a nonlinear seed-conditioned constraint or a different elimination is
required.

No complete IC candidate or measured single-target comparison is defined
by this certificate; candidate and run IDs remain null. Run
`PYTHONDONTWRITEBYTECODE=1 python3 run.py` followed by the checked launcher
`/Volumes/SSD990/cryptanalysis/sage -python audit.py` only in a new copy
of this write-once directory. The saved result files and source hashes are
the authoritative execution receipts.
