# N131 W15 four-atom quartics in a five-pair public relation formula

Two exact four-atom quartic blocks now replace four pair-output constraints and their two S3 joins in the frozen N131 W15 five-pair formula. The archived constructed relation satisfies both quartics with **one branch each**, and a full Boolean assignment satisfies all **1,200,280 CNF clauses** and **142,972 native-XOR rows** of its constructed-target circuit. The same source-bound construction reaches the public point within the one-worker, 600-second, 4-GiB gate, where the unpinned solver returns **`BOUNDED_UNKNOWN`** after 594.087 seconds of charged work. This experiment establishes the exact N131 transfer and its measured search boundary; the direct quartic encoding is substantially larger than the existing pair-output/S3 formula on the same point.

## Method and fixed input

The field is `GF(2)[t]/(t^131+t^13+t^2+t+1)` and the curve is `y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The W15 source has 16,441 usable masks and 16,381 folded columns. The target-independent prefix fixes masks `[4,17]`; the five remaining signed pairs use Frobenius rotations `[13,26,39,52,65]` and retain ten free 15-bit source masks with exact support and distinct-column constraints. The [protocol](protocol.json) freezes the previously published public point `(2309658012506412099988466246134815930289,1578526100003023531340803776621036465818)`, its residual after that prefix, both four-point target fibers, source and solver hashes, one worker, 600 seconds for construction plus search, and 4 GiB combined RSS.

For each of the first four source pairs, the [circuit](circuit.py) represents a seed sum on 15 fixed field images and a pair product on 29 diagonal images. Two four-atom quartics use the universal exact `A+wB=0` relation and `w²+w=z+a+b`; the remaining pair retains the earlier bilinear output equation. Two reciprocal S3 joins connect the three resulting outputs to one raw lift of the public residual. Source-aware products use the smaller of sparse bilinear multiplication and the existing dense Karatsuba circuit at the declared 5,000-pair threshold. All source masks, block outputs, branch witnesses, intermediate output, and allowed target-fiber flags are free in the public query.

## Constructed relation and public query

The [arithmetic control](arith_control.json) evaluates the universal quartic directly in the N131 field on the archived five-pair constructed relation and finds one accepted branch for each four-atom block. The [full circuit control](control_result.json) binds all 940 primary variables to that relation, evaluates every derived gate, and checks every clause and native-XOR row. The archived source relation has an independently recorded group lift in the prior five-pair control.

| Same public residual and W15 source | Existing pair-output/S3 formula | Two source-aware quartics |
| --- | ---: | ---: |
| AND gates | 61,363 | 343,467 |
| Variables | 97,074 | 487,378 |
| CNF clauses | 354,246 | 1,200,280 |
| Native-XOR rows | 34,509 | 142,971 |
| XCNF bytes | 21,608,680 | 105,210,044 |
| Public-query result | `CENSORED_TIME` | `BOUNDED_UNKNOWN` |

The quartics contribute 321,468 AND gates: 78 sparse field products with 170,994 bilinear pair products and 32 dense products. The last standalone pair contributes 3,799 AND gates, and the target-linear join contributes 524. On the public query, construction took 13.249585542 seconds, formula writing and hashing 0.598874166 seconds, and solver search 580.238204334 seconds, for **594.086664042 seconds** charged in total. Sampled combined RSS peaked at **854,540,288 bytes**. The solver entered search, logged 2,391 restarts and roughly 1.96 million conflicts, and reached the parent time cap without a terminal SAT or UNSAT line. The [query receipt](query_result.json), compressed [formula](query.xcnf.gz), compressed [stdout](solver.stdout.gz), and [terminal audit](terminal_audit.json) retain exact hashes and status. Timings are exploratory on an unisolated host; neither censored run supports a wall-time speedup ratio.

The [archive verifier](verify.py) checks frozen sources, target identity, the positive arithmetic and Boolean controls, the independent prior group lift, the complete decompressed formula hash and header, transcript hashes, active restarts, resource cap, and exclusive phase sum. Its result is `PASS_N131_W15_QUARTIC_BOUNDARY_ARCHIVE`. A positive constructed assignment establishes formula correctness for that relation; it does not estimate ordinary relation yield. The bounded public query supplies an ordinary-query status, not a proof that the formula is unsatisfiable.

This comparison disfavors direct four-atom quartic replacement as the next N131 solver kernel: it increases formula size by about fivefold while the same public point remains unresolved at the cap. The next algorithmic experiment should generate or reject target-compatible partial-sum families *before* expanding ten W15 masks into a large Boolean formula, with exact witness preservation and an unpinned N41 control. `candidate_id` remains `null` until a complete relation-collection and target-recovery pipeline is specified.
