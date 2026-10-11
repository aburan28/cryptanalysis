# Exact transported W6 pair join on the frozen N41 middle points

The exact transported W6 construction has **1,956 distinct pair points per Frobenius rotation**, versus 128,656 in the sparse-product relaxation, a **65.775× domain reduction**. Joining rotations 20 and 30 found one four-atom sum for the frozen positive middle point with four distinct factor-base columns. All eight target-derived middle points were exhausted over both complete exact domains. An independent Sage run rebuilt every source transport, both 1,956-point domains, and all nine joins.

## Construction and verification

The field is `GF(2)[t]/(t^41+t^3+1)` and the curve is `y²+xy=x³+1`. The source screen records `4P` rows; the target middle points are sums of `D=P+π(P)` with `π(x,y)=(x²,y²)`. The checked Sage [input producer](make_input_sage.py) found the raw `P` for each of 128 rows, verified `4P` against its screen row, and verified `x(D)=1/w` for the rotated W6 seed `w`. The [v2 protocol](protocol_v2.json) froze these preimages and the native executable before the measured join.

The native [receipt](receipt_v2.json) enumerates unordered pairs within each 64-point source window. It excludes 60 pairs per rotation whose atoms share a factor-base column, verifies every pair against the sparse-product halftrace relaxation, and indexes the complete exact right domain by group point. A query probes `M-L` for every left pair point and checks distinct columns across all four atoms at each group hit. The [independent Sage replay](sage_replay_v2.json) recomputed the same pair domains and group joins from the raw `P` coordinates, without using the native point sets.

| Measured component | Result |
| --- | ---: |
| Source points per rotation | 64 |
| Valid pair witnesses / distinct pair points, each rotation | 1,956 / 1,956 |
| Reusable source transport, pair construction, right index | 9.361375 ms |
| Frozen positive | `EXACT_FOUR_ATOM_HIT`; one group hit, one column-compatible hit |
| Positive source masks | `(53,59)` and `(1,6)` |
| Positive target-dependent query | 0.376041 ms; 1,956 probes |
| Eight target-derived controls | `COMPLETE_EXACT_NO_SUM`; 1,956 probes each |
| Nine query time sum | 3.360875 ms |
| Peak process RSS | 2,572,288 bytes |

The positive pair points are exactly `(367904714774,1204258536195)` and `(662625367342,793852298967)`, the pair points independently found by the earlier relaxed join. The four source columns are 11, 18, 0, and 20. Query times include every group probe and exact group check, while the reusable domain and index construction are separately charged. These local CPU times are exploratory without a host-isolation receipt; they measure this component, not a completed IC target query.

The first frozen [protocol](protocol.json) fed subgroup `4P` rows to code expecting raw `P` and stopped on `source transport mismatch` before any target query. Its [failure log](run.stderr) is preserved. The v2 Sage preimage reconstruction corrected that input while retaining the same native source and nine middle points. The source screen and target fixture have different curve IDs because their canonical records differ; all 128 raw points, their `4P` images, transported points, and nine target coordinates were checked on the same explicit field and curve before combining them. `candidate_id` remains `null` for this component.

The next N131 test must keep exact source-pair compatibility while preventing four-pair combinations from expanding into an infeasible full list. A target-conditioned indexed join should be judged by how many N131 pair states it materializes, how many target-derived compatibility tests it performs, and whether it produces a verified ordinary relation within the one-worker, 600-second, 4-GiB gate.
