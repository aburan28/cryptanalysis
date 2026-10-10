# Exact pair-output tables reduce N41 circuit size while preserving the public relation

**Precomputing each fixed-sum block's 80 possible `(mask, phi(pair sum))`
descriptors removes all six local pair multiplication circuits.** On the
same six-block N41 public point, the resulting frozen SAT formula has
16,915 variables and 8,968 AND gates. A pinned run recovered the saved
12-summand public relation, checked Sage replayed its leaves, and an
independent parser verified that its assignment satisfies the full
unpinned public XCNF. The unpinned one-worker SAT query reached its
120-second cap after active search. The contribution is an exact compact
finite-domain representation and a measured solver limit, not an inferred
natural-query success from the pinned control.

## Exact construction and matched circuit counts

The input is `EC1N41Ckb1h7d5e80d3c4d0` over `GF(2^41)` with modulus
`t^41+t^3+1`, subgroup order `r=549756390943`, and public point
`Q=(1458168294740,1672312028033)`. Six rotations
`[0,6,12,18,24,30]` use **B=960** subgroup-usable factor-base points
and **K=77** folded columns. Each fixed-sum block has 40 unordered
usable mask pairs. Their 160 signed group states give exactly 80 distinct
`(mask, phi(pair sum))` descriptors, each with two sign lifts.

The [circuit](circuit.py) chooses one descriptor per block with a
linear-size sequential cardinality encoding. Its output coordinate is a
binary linear combination of descriptor constants; cross-block binary
clauses reject repeated folded columns. Five S3 links connect the six
chosen outputs to the four raw preimages of the public target. The
[preflight](preflight.json) checked domain coverage for every saved pair
state and the complete four-input truth table of the sequential
one-hot encoding. The [protocol](protocol.json) freezes the source,
input, solver, seed, one-worker policy, 120-second online cap, and
4-GiB memory cap. This is proposal `Q20261009175800`, with
`candidate_id: null` for the point-decomposition stage.

| Pinned six-block formula | Rank-seven bilinear | Exact pair table |
| --- | ---: | ---: |
| Variables | 20,034 | **16,915** |
| CNF clauses | 34,993 | **31,725** |
| Native XOR rows | 8,882 | **6,822** |
| AND gates | 10,690 | **8,968** |

The pair-table formula has 480 descriptor selectors, 477 sequential
one-hot auxiliary variables including the target choice, and 2,760
cross-block column-conflict clauses. The two circuits have the same
six-block target S3 topology and saved public witness. These are exact
formula counts; no CPU speedup ratio is inferred from them.

## Frozen runs and audit

| Run | Status | Charged target-dependent wall | Peak combined RSS |
| --- | --- | ---: | ---: |
| [Pinned public-witness control](control/result.json) | `FOUND_VERIFIED_RELATION` | 0.276 s | 32.2 MB |
| [Unpinned public query](public/result.json) | `ONLINE_TIME_CAP` | 120.066 s | 178.9 MB |

The [checked-Sage audit](audit.json) replays the six saved pair sums and
12 subgroup leaves and checks both terminal receipts. The independent
[full-XCNF audit](formula_audit.json) checks the control assignment
against all **31,308 CNF clauses** and **6,822 native XOR rows** of the
unpinned public formula. Its successful evaluation proves the frozen
public instance has at least one valid assignment; the timed run
provides no search completion. Raw solver streams and source hashes are
preserved. Wall times are exploratory because this host lacks an
isolation receipt.

## N131 transfer gate

The [source-bound d13 projection](n131_table_projection.json) finds the
largest fixed-sum bucket at code `1830`: 1,102 usable mask pairs,
2,204 exact pair-output descriptors, and 4,408 signed group states per
block. A twelve-block table encoding needs 26,448 descriptor selectors,
26,436 sequential-cardinality auxiliaries, 79,308 cardinality clauses,
and 290,928 cross-block column-conflict clauses under the audited
`K=4,134` column policy. These counts replace the earlier direct
three-block table's 2.91-TB point-storage demand with a finite-domain
circuit; the outer S3 arithmetic and target search are still required.

The next method must propagate the public target through two or more
partial blocks before enumerating their combinations. The saved N41
witness and full public formula give a preservation check, and the
N131 descriptor counts give a concrete representation budget. The
current N41 unpinned timing does not support an N131 ordinary-query
promotion under the 600-second/4-GiB gate.
