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
