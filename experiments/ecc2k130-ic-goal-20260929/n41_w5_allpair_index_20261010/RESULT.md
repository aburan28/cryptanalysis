# Five exact pair-output indices isolate the N41 upper-chain SAT gate

Indexing **all five** W5 leaf-pair outputs removes their arithmetic S3
links from the degree-41 ten-summand public-point formula. A complete
assignment from the independently replayed public relation satisfies
every clause and native XOR row in the unpinned and fixed-selector
formulas. With all five correct pair outputs fixed, CryptoMiniSat still
reached the frozen 20-second cap after active search. The four upper S3
links are the measured search gate for this representation.

The curve is `EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2^41)` with polynomial `t^41+t^3+1`, subgroup order
`549756390943`, and public point
`Q=(1458168294740,1672312028033)`. Ten source leaves use rotations
`[0,0,8,8,16,16,24,24,32,32]`, **B=170** usable factor-base points
before folding, and **K=14** folded columns. Each equal-rotation pair
uses the independently [checked 264-entry output index](../n41_w5_pair_index_20261010/RESULT.md).
The [circuit](circuit.py) gives each pair a linear-size exactly-one
selector and constrains its two rational masks and inverse-Frobenius
output coordinate to the selected entry. The existing distinct-column
constraints cover all ten leaves. A SAT model requires final raw-point
replay because transformed coordinates omit signs.

The [frozen protocol](protocol.json) binds code, index, public target,
source geometry, solver, checked Sage runtime, resource caps, and the
known public-relation selectors `[240,172,138,253,178]`. Pairwise leaf
swaps put every control mask pair in canonical order without changing
its raw group sum. The [preflight](preflight.json) checks a full known
assignment against the public formula and two progressively pinned
forms:

| N41 five-pair formula | Public | Four known selectors | All five known selectors |
| --- | ---: | ---: | ---: |
| Variables | 15,676 | 15,676 | 15,676 |
| CNF clauses | 93,985 | 93,989 | 93,990 |
| Native XOR rows | 5,573 | 5,573 | 5,573 |
| AND gates | 7,086 | 7,086 | 7,086 |
| Complete public-relation assignment | pass | pass | pass |

The first attempt to start the all-fixed solver hit a transient filesystem
`ENOSPC` while creating its stdout file, **before search**. Its
[failure receipt](failure_v1.json) is separate from the solver evidence.
After workspace free space recovered, the unchanged frozen formula and
runner were retried. The [all-fixed result](all_fixed_query/result.json)
is `CENSORED_TIME` at 20.160 seconds, with 383 logged search restarts,
31,948,800 bytes sampled solver peak RSS, zero model lines, and empty
stderr. This is a capped search observation on an unisolated host, not an
UNSAT result. The [gate decision](gate_result.json) records the
four-fixed and unpinned SAT stages as `NOT_RUN_GATE_CLOSED`; the
[terminal audit](terminal_audit.json) verifies source hashes, all three
full-formula checks, the pre-search failure, and the active capped retry.

The known assignment proves that exact pair-output membership preserves
the public relation. The all-fixed cap shows that simply tabulating
leaves does not make the upper S3 SAT chain a useful target-conditioned
selector. The existing [exact N41 group lookup](../n41_two_free_pair_occupancy_20261009/README.md)
already demonstrates that raw curve addition handles fixed pair-output
families directly; its N131 transfer bound rules out literal fixed-prefix
enumeration. The next algorithm gate is symbolic rejection of whole
target-conditioned seed-sum families, using the audited W14 pair inverse
without enumerating its enormous output domain. This stage retains
`candidate_id: null` while the goal advances toward ordinary degree-131
relations, novel rank, verified factor logs, and the paired one-target
rho comparison.
