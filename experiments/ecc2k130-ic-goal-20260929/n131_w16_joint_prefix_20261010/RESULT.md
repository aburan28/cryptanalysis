# One target-coupled W16 circuit for 32 signed first-pair prefixes

A single W16 five-pair XCNF now searches **32 signed first-pair prefixes and
their four residual-target preimages at once**. The source and five-pair
equations are constructed once; one-hot choice variables select the exact
residual target and conditionally exclude the chosen prefix's two folded
columns. A full constructed twelve-point relation satisfies the resulting
formula with all **128 choices left unpinned** in the search input. This
removes repeated source-circuit construction from the 32-prefix width gate,
while retaining each prefix's exact target and distinct-column constraints.

For any selected choice, the one-hot condition sets exactly one residual
reciprocal coordinate. Each of the ten remaining source masks is forbidden
from the selected first pair's columns. The other nine masks have the same
W16 membership, pair, seed-sum, and distinct-column equations as the
single-prefix circuit. Thus the projected solutions of this formula are
exactly the union of solutions of its 32 separately specified residual
circuits. The [circuit source](circuit.py) uses the already audited W16
decision-graph membership encoding; the [prefix manifest](prefixes.json)
fixes all source points and residuals before formula construction.

## Frozen constructed control

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`. Prefix zero is the public signed first pair
from the archived constructed twelve-point control. The other 31 choices
come from a fixed deterministic source-mask and sign stream. The method
does not use the remaining ten control masks when building or querying its
formula. The [checked-Sage geometry audit](audit.json) independently rebuilt
all 64 raw leaves, checked their W16 masks and folded columns, all 32 raw
and cofactor-projected pair sums, and every residual target and four-element
target fiber. It also confirmed that the archived residual appears at prefix
zero. The checked local [Sage runtime](sage_runtime_info.json) was saved
before the jobs.

| Constructed W16 residual circuit | One prefix, compact membership | Joint 32 prefixes |
| --- | ---: | ---: |
| Choice branches | 4 | **128** |
| Variables | 181,640 | 198,137 |
| CNF clauses | 366,295 | 425,729 |
| Native-XOR rows | 34,600 | 34,729 |
| XCNF bytes | 17,908,837 | **26,491,206** |
| Control circuit construction | 13.324 s | 13.590 s |

The joint [full-assignment control](control.json) satisfies all 425,729 CNF
clauses and 34,729 native-XOR rows and independently closes the projected
group sum to the original target. Its selected validation choice is `2`
(prefix zero, preimage two); the solver query had no pinned choice. The
individual construction intervals are exploratory on a contended host.
The exact structural saving is one source core and one formula serialization
for 32 choices, rather than 32 separate source cores and formulas; the two
construction timings alone do not establish an isolated-host speedup.

## Bounded search and next gate

The [one-target, one-worker query](query.json) rebuilt a byte-identical joint
formula from the [frozen protocol](protocol.json). CryptoMiniSat made 35
recorded restarts and returned no model before the 115.060-second safe wall
stop: 11.513 seconds formula construction and 103.547 seconds solver interval.
Sampled solver CPU was **11.143 seconds** and combined peak RSS was
**490,766,336 bytes**, below the 4-GiB cap. Its status is `CENSORED_TIME`;
the [independent receipt audit](audit.json) binds the formula, input,
source, raw transcript, timing cap, and exact geometry. This constructed
control is known satisfiable, so the row measures a bounded model-search
attempt, not ordinary relation yield.

The next solver gate is a paired, isolated-CPU run of the frozen one-prefix
and joint-prefix formulas with identical solver binaries, flags, resource
caps, and complete target-dependent accounting. It should report solver CPU,
wall, conflicts, memory, and any independently replayed group model. If the
joint search remains censored after a full CPU budget, the next method step
is target-conditioned partial-output generation on the existing N41 public
control, followed by an exact N131 work/memory bound before a fresh ordinary
query. Factor-log rank, verified one-target scalar recovery, and same-point
rho remain the later full-pipeline gates; `candidate_id` is `null` here.
