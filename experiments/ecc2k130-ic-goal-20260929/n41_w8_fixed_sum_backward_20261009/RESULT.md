# The public target restricts the preceding partial sum to 640 exact coordinates

**Subtracting the final fixed-sum pair from each of the four raw preimages
of the N41 public point gives exactly 640 distinct residual phi
coordinates.** This exact target-conditioned domain is imposed at the
root of a five-pair S3 tree, before the solver chooses any of its forward
pair descriptors. The saved six-block public relation survives the
restriction, passes the complete unpinned XCNF, and is independently
replayed in checked Sage. The unpinned one-worker SAT query reached its
120-second cap after active search, so the domain cut alone did not
extract the relation within this envelope.

## Exact backward completion

The frozen public point is `Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`, with subgroup order `r=549756390943`.
For each raw preimage `T` satisfying `4T=Q` and each signed last-pair
state `P_5`, [reachability.py](reachability.py) computes `R=T-P_5`,
checks `R+P_5=T`, and stores `phi(R)=1/(x(R)+1)` with the exact target
branch and final state. Four raw preimages times 160 signed states give
**640 distinct residual points and 640 distinct phi coordinates** on
this input. Their field-coordinate density is `640/2^41`, approximately
`2.91e-10`; this is a domain count, not a natural solver yield.

The [circuit](circuit.py) selects one target-derived residual first,
then chooses one of 80 exact `(mask, phi(pair sum))` descriptors for each
of the first five pair blocks. Cross-block clauses also exclude any
residual whose final pair repeats a folded factor-base column. Four S3
links connect the five forward blocks to the chosen residual. The
[preflight](preflight.json) verifies the 640-entry domain, exact group
construction, saved public witness, and cardinality encoding. The method
uses six rotations `[0,6,12,18,24,30]`, **B=960** actual usable subgroup
points, and **K=77** folded columns. It is proposal `Q20261009180400`
with `candidate_id: null` for this point-decomposition stage.

| Frozen six-block formula | Exact count |
| --- | ---: |
| Variables | 15,278 |
| Pinned CNF clauses / native XOR rows | 35,143 / 5,649 |
| Unpinned CNF clauses / native XOR rows | 34,768 / 5,649 |
| AND gates | 7,432 |

## One-worker public query

| Run | Terminal status | Charged target-dependent wall | Peak combined RSS |
| --- | --- | ---: | ---: |
| [Pinned saved-witness control](control/result.json) | `FOUND_VERIFIED_RELATION` | 0.303 s | 34.2 MB |
| [Unpinned public query](public/result.json) | `ONLINE_TIME_CAP` | 120.013 s | 256.6 MB |

The public interval includes 5.586 ms for raw target preimages, 37.900
ms for the exact target residual domain, the remaining formula build,
119.891 s of solver execution, and model/terminal checking. The first
two values are subsets of the 118.913-ms formula/query phase; they are
not added twice. The [full-XCNF audit](formula_audit.json) independently
checks the saved control assignment against every unpinned public clause
and native XOR row. The [checked-Sage audit](audit.json) replays the
saved six-pair group relation and verifies both terminal receipts.
Thus the public status records a bounded search, with a known admissible
assignment in the exact formula.

The repository volume filled immediately before the run. The frozen
execution was staged in `/private/tmp/cryptanalysis-backward-20261009`
and copied back byte-for-byte; the [protocol](protocol.json) still
matches all 20 executed source hashes. A fresh Sage runtime probe failed
before launch with `ENOSPC`, so the [runtime provenance](runtime_source.json)
records reuse of the preceding verified output whose accepted manifest
hash matched the live manifest. After the timed public run, the checked
launcher produced [fresh runtime output](sage_runtime_info_postrun.json)
that was byte-identical to the saved receipt, and it ran the independent
audit. Solver timings here are exploratory without host isolation.

## Next target-conditioned gate

One backward pair gives a compact root domain but did not make SAT
finish. The d13 N131 geometry has 4,408 signed states per fixed-sum
pair. Two backward pairs from four raw target preimages have at most
`4*4408^2=77,721,856` group states. A direct 34-byte encoding of both
131-bit point coordinates would need 2,642,543,104 bytes before
descriptors and indexing. The next experiment should build a packed
two-pair backward table with exact sign/column descriptors, test
same-target family rejection against the saved N41 relation, and
measure total construction plus membership cost under 600 seconds and
4 GiB before promoting an N131 ordinary query. The remaining forward
search still needs a complete source-bound work estimate.
