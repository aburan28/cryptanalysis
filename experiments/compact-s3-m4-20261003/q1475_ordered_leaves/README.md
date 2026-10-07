# Q1475: ordered raw leaves in the compact chained-S3 solver

Q1475 changes one part of the Q1472/Q1474 four-summand SAT input: it adds
exact CNF clauses requiring the four raw normal-basis x-coordinate integers
to satisfy `x0 < x1 < x2 < x3`. The existing chained-S3 equations, exact
root propagator, native binary, factor bases, target inputs, decision policy,
and resource limits remain the paired baselines. The [design protocol](design_protocol.json)
was committed before construction of the six new inputs; the full
[protocol](protocol.json) freezes their hashes and the solver snapshot before
runs.

The restriction is sound for the desired four-distinct-column relation. Its
four raw x values must be distinct. Sort the four signed raw points, form
new pair midpoints from the first two and last two, and use commutativity of
the group sum to retain the same target preimage and public point. The CNF
comparator was exhaustively tested for two- and three-bit inputs, including
all auxiliary-variable assignments. A pinned sorted-witness control at each
field degree checks the complete formula and solver.

| Degree | Exact curve ID | Actual usable base B | Folded columns K | Enumerated-set digest |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 2,756 | 26 | `cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 1,934,066 | 11,651 | `1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325` |

The N53 and N83 stage IDs are
`PS1N53Ckb1fb2756PDP4hybridh76d17c3d67b7` and
`PS1N83Ckb1fb1934066PDP4hybridh6360052acf66`, respectively. Each case has
a `PS1...W...R1` stage run ID. This is still a PDP stage proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`.

The frozen run order is: sorted pinned N53 and N83 controls; the Q1474 N53
known-representable full 428-preimage public target; Q1467's known-
representable unpinned N83 target; and Q1467's N53 and N83 ordinary queries.
The four free-leaf cases match prior public points, workloads, bases, and
native limits. Every case has a 250,000 pair-admission cap, 1,000,000 SAT
conflicts, a 60-second native wall cap, and a 75-second external safeguard.
All six cases run once in order and retain censored and failed attempts.

An accepted model must satisfy every CNF clause, all three S3-root links,
the leaf order, the exact base policy, four distinct folded columns, the
selected raw target preimage, a signed raw group sum, and the public subgroup
point. SAT propagations, field primitive calls, wall time, and memory are
recorded separately. Pinned controls do not estimate natural yield; one
ordinary query per degree cannot establish a yield rate. Without successful
free-leaf N83 work and the remaining IC stages, no complete N131 `2^x` or
sub-`2^61` claim follows.

## Measured result

The [independent audit](archive_audit.json) regenerates the six CNFs,
verifies every frozen hash and run receipt, and replays both pinned SAT
models against the CNF, ordered leaves, S3 roots, exact base policy,
distinct columns, raw target preimage, and public group point.

| Frozen case | Native result | Verified relation | SAT propagations | Field mul / sqr / inv calls | Eligible exact joins |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 sorted pinned control | SAT | 1 | 82,667 | 209 / 1,236 / 18 | 0 |
| N83 sorted pinned control | SAT | 1 | 218,650 | 258 / 2,180 / 20 | 0 |
| N53 known-representable full coset | 60 s wall cap | 0 | 328,558,707 | 12,090,373 / 51,150,158 / 9,795 | 213 |
| N83 known-representable unpinned | 60 s wall cap | 0 | 360,690,656 | 382,810 / 2,573,942 / 7,691 | 1 |
| N53 ordinary | 60 s wall cap | 0 | 338,294,876 | 12,267,189 / 51,886,018 / 9,439 | 214 |
| N83 ordinary | 60 s wall cap | 0 | 318,703,689 | 382,810 / 2,573,942 / 7,691 | 1 |

All four free-leaf cases are censored, so each reported work vector is a
prefix of this solver's search, not a successful decomposition cost. The
matched Q1474 N53 full-coset baseline made 49 eligible exact joins and
16,857,549 field multiplications at its 60-second cap; Q1475 made 213 joins
and 12,090,373 multiplications on that same public point. The matched Q1472
N53 ordinary baseline made 49 joins and 17,049,276 multiplications; Q1475
made 214 joins and 12,267,189 multiplications. At N83, both ordered
free-leaf cases still reached only one eligible exact join, the same count
as their Q1472 baselines. The altered prefixes establish a search-behavior
change, not a solved-query or CPU speedup. Wall intervals are exploratory
because the host has no isolation receipt.

The immediate method gate remains a verified free-leaf N53 relation on the
known-representable full public-target coset, followed by a successful N83
control and an ordinary N83 panel. Restricting permutation symmetry alone
does not meet it. A useful next variant must condition both pair domains on
the target earlier than the existing 250,000-pair exact-join admission point.

## Reproduce the audit

```sh
python3 experiments/compact-s3-m4-20261003/q1475_ordered_leaves/prepare_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1475_ordered_leaves/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1475_ordered_leaves/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

These checks replay the archived evidence; they do not rerun the native
60-second cases. Each case's raw stdout, stderr, model when SAT, and
source-bound receipt are retained under `runs/`.
