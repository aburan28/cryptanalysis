# Complete first-half family census with an independent reciprocal S3 join

The frozen N41 first-half family has **1,711 eligible target-derived right-middle points** and zero exact four-atom suffix hits. The known positive middle point, included as a correctness control, has one compatible exact suffix witness. A reciprocal S3 root solver and a direct group subtraction join agree on all 1,712 statuses and exact hit counts. Checked Sage replay reconstructs every derived middle point and the positive witness.

## Geometry and input law

The field is `GF(2)[t]/(t^41+t^3+1)`, the curve is `y²+xy=x³+1`, and the subgroup order is `549756390943`. The four suffix atoms come from W6 source windows at Frobenius rotations 20 and 30. There are 64 source rows per rotation and 1,956 distinct-column pairs per rotation. The source has `B=256` usable projected points and `K=26` folded columns. This is a component experiment with `candidate_id: null`.

The public raw preimage `U` and fixed second first-half pair `B` are bound by the [panel](panel.json). For every eligible first pair `A` in the frozen first-half source, the Sage generator forms `V=U-A-B`, retaining nonidentity, nonzero-x, trace-zero-reciprocal, distinct `V` values whose first four source columns are distinct. It retains **all 1,711** eligible values after a seeded shuffle. The positive `V` from the prior verified eight-atom witness is added separately. The [exact input](exact_input.txt), [direct-join protocol](protocol.json), and [S3 protocol](protocol_s3.json) freeze the source, input, binaries, host, and one-worker 600-second/4-GiB envelope before their respective runs.

## Two complete joins

The direct join indexes the 1,956 exact right-pair points. For each target `V`, it probes `V-L` for all 1,956 exact left-pair points `L`, checks four distinct folded columns, and replays the group sum.

The second join uses reciprocal coordinates `z=1/x`. For `L+R=V`, the curve's third summation equation is

`(1+(z_L z_V)²) z_R² + (z_L z_V) z_R + z_L²+z_V² = 0`.

It solves this quadratic by halftrace when its trace condition holds, looks up only the resulting right-pair reciprocals, and then checks the full group equation and columns. For odd degree 41, halftrace supplies both roots of `h²+h=β` whenever `Tr(β)=0`; the linear case is handled separately. This route enumerates every exact right-pair coordinate compatible with each `(L,V)` without using the direct join's group-subtraction lookup.

| Frozen N41 panel | Direct group join | Reciprocal S3 join |
| --- | ---: | ---: |
| Queried middle points | 1,712 | 1,712 |
| Exact pair probes per point | 1,956 | 1,956 |
| Positive compatible four-atom witnesses | 1 | 1 |
| Eligible controls with a group hit | 0 / 1,711 | 0 / 1,711 |
| Indexed S3 root candidates, all points | — | 4 |
| Sum of per-query elapsed time | 3.766677787 s | 4.710697377 s |
| Reusable pair/index setup | 0.005713417 s | 0.011225417 s |
| Peak RSS | 2,654,208 B | 2,621,440 B |

The [direct receipt](receipt.json) and [S3 receipt](s3_receipt.json) retain one status, probe count, hit count, and query time per point. The [audit](audit.json) checks both frozen source hashes and every paired row. The [Sage replay](sage_replay.json) rebuilds the two exact suffix source windows, independently reconstructs the first-half source used to derive all controls, checks `U-A-B=V` and reciprocal trace for each, and replays the positive four-atom group sum. The positive suffix columns are `[11,18,0,20]`; together with its first-half columns `[8,1,10,13]`, the witness has eight distinct folded columns.

These times are exploratory stage measurements on an unisolated CPU. Each total above is the sum of 1,712 separate component queries, with reusable setup reported separately; the input law fixes one first-half pair and generates controls from the public preimage. The [earlier complete N41 public-point fiber](../n41_target_projection_20261011/RESULT.md) has 12 valid eight-column rows when both first-half pairs vary, so the current zero-hit census specifically measures the cost of fixing this one pair. It does not estimate yield over the full first-half space.

## Next design step

The complete census makes the next gate concrete: vary the second first-half pair through a target-conditioned constraint while preserving both first-half pairs unresolved at the filter stage. An exact or sound over-approximate seed/product condition should reject families *before* enumerating their pair combinations, then be measured against the 1,956-pair direct join and the existing complete N41 fiber. Only a condition with a source-bound W18 memory and work projection under the N131 4-GiB/600-second gate merits promotion.
