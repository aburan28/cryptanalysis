# Exact t-weight-four base and ordinary N53 solver gate

Q20261010174100 enumerates the complete normal-basis t-weight≤4 base on
`EC1N53Ckb1hf77aab617904`: **151,792 actual usable points** before
sign/Frobenius folding and **1,432 effective columns**. It examines all
317,682 nonzero masks through 5,994 full Frobenius orbits. The complete
packed-key SHA-256 is
`dc893cbf63b84a1f771a8857fb8e7e82fa3c8164d11762e4969a107a78346778`.
The independent audit used the other x lift of each t value and field
Frobenius rather than the producer's mask permutation. It reproduced the
exact key bytes and all per-weight counts. The weight-three prefix also
reproduced Q20261010173300's `B=11342`, `K=107`, and digest.

| Bound | Nominal masks | Frobenius orbits | Actual `B` | Folded `K` | Enumerate s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| t weight≤3 | 24,857 | 469 | 11,342 | 107 | 1.23 |
| t weight≤4 | 317,682 | 5,994 | 151,792 | 1,432 | 14.67 |

Times are exploratory. All rational orbit representatives projected to
nonidentity subgroup points, and no two such orbits collided after
cofactor projection. The weight-four increment supplied 1,325 rational
orbits and 1,325 new columns. The base receipts retain the exact input
and source hashes, raw counts, and process RSS boundary.

Q20261010174500 then built a balanced three-link t-S3 formula on the
**existing ordinary public target** `W74f2979b3e68`, using the exact
weight-four base. The target's 428 raw cofactor preimages collapse to
214 distinct t values. The frozen formula has 27,447 variables, 89,088
CNF clauses, 1,113 native XOR rows, and 25,281 shared AND gates. It does
not expand S5. The serialized formula and solver receipt pass
the archive audit.

| Ordinary N53 run | Status | External cap | Child CPU | Peak child RSS | Verified relations |
| --- | --- | ---: | ---: | ---: | ---: |
| t weight≤4, default CryptoMiniSat | `BOUNDED_UNKNOWN` | 120.02 s wall | 22.20 s | 137.6 MB | 0 under cap |

The solver was killed by the external wall cap while active search was
visible in its archived output. It did not reach the one-million-conflict
cap, and the host load was high during the run. This row is censored: its
zero verified relations is not a natural-yield estimate or a proof of
unsatisfiability. The old x-weight≤3 Q1410 formula uses the same curve
and target but a different exact base (`B=24062`, `K=227`), so its 69.58 s
exploratory solver interval is a geometry-plus-encoding control, not a
paired CPU speedup comparison.

Both proposals retain null `candidate_id`/`run_id` and `ISO0`. The
weight-four freeze SHA-256 is
`ab304e5f370d94eed660966db2627a05ebe83cd9f1606562123316659e8b754e`;
the ordinary gate freeze SHA-256 is
`2cb55bd207d70d3b6b1405e5608956d35c3d936db5563a8904823d3506926b00`.
Each `audit.json` records PASS. Move an audit output aside before replaying
its auditor, which refuses to overwrite an existing result.

The next measurement should give the **same frozen formula** enough child
CPU time to reach either a SAT model or the conflict cap, while retaining
all wall and resource costs. A natural relation would then require exact
base and signed group-law replay, rank novelty, and a comparable N83 base
before any degree-131 projection.
