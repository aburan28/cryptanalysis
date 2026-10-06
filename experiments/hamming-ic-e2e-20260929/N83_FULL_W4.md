# Complete N83 weight-four geometry for a five-summand PDP

The [N83 next-calculus screen](N83_NEXT_CALCULUS.md) measured deterministic
prefixes of weight-four normal-basis masks. A prefix has a compact base but
requires a solver to enforce a 4,000-orbit whitelist. This follow-up measures
the **complete** weight-four mask family. The exact raw x predicate is then
normal-basis Hamming weight three **or** four, followed by rational lifting
and cofactor-four projection. It is a simpler input rule for an implicit S3
chain than the prefix whitelist. It does not yet make a viable PDP solver.

The [protocol](n83_full_w4_protocol.json), producer, and independent replay
were committed and pushed in `5101f28f` before execution. The starting
4,000-orbit geometry and representative-set SHA-256 values are pinned in that
protocol. The field is `GF(2^83)` in the polynomial basis with modulus
`u^83+u^7+u^4+u^2+1`; the curve is `y²+xy=x³+1`, with subgroup order
`r=2417851639230796216685689` and cofactor four. Its immutable curve ID is
`EC1N83Ckb1h2bcb59d56ad6`. No complete IC candidate is specified, so
`candidate_id: null`.

## Exact result

The checked-Sage [producer](runs/n83_full_w4_geometry_v1/geometry.json)
completed all `C(83,4)/83 = 22,140` cyclic weight-four mask orbits under the
900-second cap. Its independent [replay](runs/n83_full_w4_geometry_v1/sage_replay.json)
used Sage `lift_x`, checked each checkpoint, verified the entire projected
point set and representative set, and matched their SHA-256 digests. The
saved Sage runtime identities and raw stdout/stderr are in the run directory.

| W4 mask orbits | Rational W4 orbits | Actual usable base B | Folded columns K | Four-sum multisets / r | Five-sum multisets / r | Pair states `83 K²` |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4,000 | 2,015 | 423,964 | 2,554 | 0.000557 | 47.21 | 541,402,028 |
| 8,000 | 3,985 | 750,984 | 4,524 | 0.00548 | 823.28 | 1,698,725,808 |
| 12,000 | 6,048 | 1,093,442 | 6,587 | 0.0246 | 5,387.31 | 3,601,251,227 |
| 16,000 | 8,051 | 1,425,940 | 8,590 | 0.0712 | 20,318.82 | 6,124,412,300 |
| 20,000 | 10,051 | 1,757,940 | 10,590 | 0.1646 | 57,864.45 | 9,308,292,300 |
| **22,140** | **11,126** | **1,936,390** | **11,665** | **0.2423** | **93,832.98** | **11,293,994,675** |

All 11,126 rational W4 orbits projected to nonidentity subgroup points;
none duplicated the W3 base or another W4 projected orbit. The final base
contains exactly `166 × 11,665` distinct points before folding. The producer
took 267.6 seconds with 858.3 MB peak RSS; the replay took 411.3 seconds.
Those are exploratory construction and correctness costs on an unisolated
host, not controlled speedup measurements.

The four-sum multiset ratio remains below one even for the full W4 family:
four-sum support is at most 24.23% of uniform subgroup targets. The five-sum
ratio is an average count, **not** a measured coverage or yield rate. The
complete W4 base gives the simplest measured normal-weight predicate for a
five-summand algebraic pilot, but its 11,665-column relation problem is much
larger than the 4,000-orbit prefix's 2,554 columns.

## Resource boundary and next gate

A plain unordered pair table on this base would require
`C(1,936,391,2) = 1,874,804,084,245` entries. Even a bare 16-byte sum key
per entry would occupy **29,996,865,347,920 bytes** before witnesses,
hashing, allocation, or query state. Copying the N53 root-index design would
generate 11.29 billion pair states. Neither complete table was built here.
The earlier [N83 five-sum trial](../pdp-scaling/five-sum-20260928/RESULTS.md)
also reached a quadratic pair-table memory cap on a different 130,604-point
base. A compact implicit S3 chain is the next algorithmic gate.

The [weight-three-or-four XCNF counter](weight34.py) now exists and its
[exhaustive seven-input control](test_weight34.py) passed all 128 truth-table
assignments through CryptoMiniSat. This tests only the cardinality predicate,
not its equivalence to a five-point group decomposition. The next pilot must:

1. Freeze one planted five-point N83 instance and its exact public target.
   Prove the chosen S3-chain/point-lift ideal matches the intended projected
   relation on a small exhaustive control, including all rational
   cofactor-four target fibers and exceptional cases.
2. Measure positive-control solver time, memory, branch totals, and raw
   failures under a fixed limit, then independently replay every witness as
   a five-point group sum and subgroup relation.
3. Advance to a frozen unseen ordinary public target only if the planted
   control is solved and replayed within its limit. Record every failed or
   timed-out branch; do not infer natural yield from planted success.

No N83 ordinary-query PDP, verified relation, DLP, paired rho reference, or
speedup has been measured. The primary one-target online comparison remains
unknown.
