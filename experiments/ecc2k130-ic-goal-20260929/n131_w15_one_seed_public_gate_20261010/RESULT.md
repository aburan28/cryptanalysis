# A fixed W15 block seed gives an exact one-target density gate

Fixing the first constrained four-atom block to mask-XOR seed **13,686**
leaves an exact group-wide mean of **1.0522519586** signed twelve-point
tuples per uniformly selected subgroup target, before cross-pair
folded-column exclusions. The constructed N131 witness satisfies all
**436,755 CNF clauses and 43,272 native-XOR rows** of this restriction.
The frozen published-point query entered active CryptoMiniSat search and
reached `CENSORED_TIME` after **592.052 s** of target formula construction
plus search under a 600 s, one-worker, 4 GiB gate. The [terminal audit](terminal_audit.json)
verified the archived public XCNF byte for byte against the earlier
unrestricted formula: only 30 seed clauses and the header count changed.

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, with subgroup order
`680564733841876926932320129493409985129`. The W15 source has
**B=197,292** subgroup-usable factor-base points and **K=16,381**
signed-Frobenius columns. The six pair rotations are `0,13,26,39,52,65`.
The [protocol](protocol.json) fixes the published point, seed, source and
solver hashes, support count, resource limits, and solver flags before the
query. The [checked Sage runtime](sage_runtime_info.json) was saved before
the measured Sage job. The [complete constructed control](control.json)
uses the prior independently group-replayed twelve-atom witness with the
same seed and checks every clause and native-XOR row of the new formula.

Let `c_s` count signed unordered source-pair states with distinct folded
columns and seed `s`. The exact [census](../n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv)
has `c_13686=16,576`, `N=Σ_s c_s=540,579,832`, and
`S=Σ_s c_s²=8,918,874,017,088`. The one-seed tuple count is
`N² S c_13686²`; division by the subgroup order gives the stated mean.
It is a source-density upper bound for row-valid tuples under the uniform
target law, not a measured relation yield on the published point.

| Published-point stage | Frozen result |
| --- | ---: |
| Target-dependent formula construction | 2.429 s |
| Solver search | 589.623 s |
| Construction plus search | 592.052 s |
| Sampled peak combined RSS | 860,749,824 B |
| Last logged approximate conflicts / restarts | 2.468 million / 2,569 |
| Terminal status / solver stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| SAT or UNSAT line / model lines | none / 0 |

The [result](result.json) preserves the target, exact online stage boundary,
formula hash, full [solver log](solver.stdout.txt), stderr, and resource
receipt. The [byte-level auditor](audit.py) checked that all 436,725 old
CNF clauses and 43,279 native-XOR rows are unchanged in the public formula.
This remains a proposal-stage method with `candidate_id: null`: the query
did not produce a relation row within its cap, so useful rank, factor-base
logs, and one-target IC online time are not measured here. CPU wall times
are exploratory on this host without an isolation receipt.

The next public gate keeps a predeclared family of eight seeds, whose exact
group-wide tuple mean is 8.354 before cross-pair exclusions, and enforces
the independently checked trace-zero target fiber.
