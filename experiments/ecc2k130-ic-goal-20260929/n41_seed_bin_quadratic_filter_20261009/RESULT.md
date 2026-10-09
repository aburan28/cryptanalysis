# An exact N41 public-point relation from seed-bin screening; all quadratic bin ranks saturate

A 16-equation filter per suffix seed-sum bin found the first ordinary eight-column relation on the frozen N41 public point after **513,088 valid prefixes**. The target-dependent search took **26.957 seconds** with one worker and **9,388,032 bytes** peak RSS, including filter evaluation, exact pair lookup, column checks, and native group replay. [Independent installed-Sage replay](resolve16_audit.json) checked the eight source points, subgroup membership, folded columns, pair indices, filter acceptance, and equality with the public point. The [full independent GF(2) rank audit](saturation_audit.json) established a second result: every one of the **3,969** seed bins has quadratic-feature rank exactly `min(bin size, 821)`. Thus the useful N41 equations come from finite-support interpolation, with no extra rank defect in this feature family.

## Frozen instance and exact method

| Item | Value |
| --- | --- |
| Curve | `EC1N41Ckb1h7d5e80d3c4d0`; `GF(2)[t]/(t^41+t^3+1)`; `y^2+xy=x^3+1` |
| Subgroup order | `549756390943` |
| Public target | `Q=(1458168294740,1672312028033)` |
| Source | Four W6 windows at rotations `0,10,20,30`; actual usable `B=256`; folded columns `K=26` |
| Pair domains | `1,956` distinct-column pair states per window |
| Proposal | `Q20261009232800`; complete-pipeline `candidate_id` and `run_id` remain `null` |
| Search cap | One worker, 120 seconds target-dependent wall time, 4 GiB RSS, at most 600,000 valid prefixes |

The exact suffix census gives **1,583,568** distinct sign-orbit `x` coordinates for the two last pair domains, partitioned by their nonzero six-bit seed sums `(s,t)` into 3,969 bins of size 128–832. The [producer](production.json) retained every `x` and its pair-state witness. For each bin, [M4RI rank extraction](rank16_result.json) formed the 821 Boolean features consisting of a constant, 40 nonconstant `x` bits, and their 780 pairwise products. It selected up to 16 exact vanishing equations from the right kernel, then checked every selected equation against every exact coordinate in its bin. The fixed-size [filter table](filters16.bin) is 6,620,292 bytes and contains 63,488 active equations; one bin has feature rank 821 and no equation.

For a first-two-pair prefix, the [resolver](resolve16.cpp) computes `R=Q-P_0-P_1` and evaluates the bin equations on `x(R)` before choosing either suffix pair leaf. For each surviving right seed, it visits only the corresponding last-pair bucket, computes the required left-pair point, and looks it up in a one-pair point index. A hit must pass the eight distinct folded-column test and exact group equality. The online implementation materializes four small N41 pair domains and a 1,956-entry left-pair index; its quadratic filters were produced from the target-independent exact suffix support.

## Public-point measurements and verification

| Frozen stage | Status | Exact count or time | Peak RSS |
| --- | --- | ---: | ---: |
| Suffix sign-orbit production | `EXACT_X_ORBITS_WRITTEN` | 1,583,568 orbits; 45.309 s setup | 38,682,624 B |
| Eight-equation rank extraction | `EXACT_QUADRATIC_BIN_FILTERS` | 31,744 equations; 6.198 s setup | 47,890,432 B |
| Sixteen-equation rank extraction | `EXACT_QUADRATIC_BIN_FILTERS` | 63,488 equations; 17.567 s setup | 51,314,688 B |
| Eight-equation public panel | `COMPLETE_PANEL` | 8,192 valid prefixes; 135,514 surviving bins; 0.164 s query | 5,406,720 B |
| Sixteen-equation public panel | `COMPLETE_PANEL` | Same 8,192 prefixes; 8,710 surviving bins; 0.431 s query | 8,716,288 B |
| Sixteen-equation exact resolver | `FOUND_VERIFIED_RELATION` | 513,088 valid prefixes; 26.957 s online | 9,388,032 B |
| Independent installed-Sage row replay | `PASS_INDEPENDENT_SAGE_ORDINARY_RELATION_REPLAY` | 256 source points; 7,824 pair states; 128 sampled exact suffix orbits | 291,913,728 B |
| Independent all-bin GF(2) elimination | `PASS_INDEPENDENT_ALL_BIN_GF2_RANK` | 1,583,568 coordinates; 3,969 bins; 166.192 s audit | 225,722,368 B |

The 16-equation resolver examined **618,198** ordered first-two-pair combinations, discarded **105,110** for repeated folded columns, and evaluated **2,036,446,272** target-conditioned seed-bin families over the remaining prefixes. Its equations rejected **2,035,901,788** families while both suffix pair leaves were still unchosen. It visited **15,744,742** right-suffix pair candidates after seed-bin and column filtering, found three exact left-index point hits, and verified one ordinary relation. The first witness is pair-state indices `[316,101,861,1057]`, source point indices `[[5,24],[1,41],[15,53],[20,39]]`, and folded columns `[9,18,14,0,10,12,4,20]`. Its residual coordinate is `332635421840`. The independent Sage audit also reproduced the first valid-prefix ordinal **513,088** and the earlier exact census's first witness.

The native resolver's target-independent input, pair-domain, index, and filter setup took **0.0395 seconds**. The 26.957-second online interval starts at the first target-minus-prefix operation and ends after native relation verification. The table construction times above are separate setup receipts. CPU wall times came from an unisolated host and are stage diagnostics; this run was not a complete IC candidate or a matched same-point rho comparison.

Two frozen input-builder attempts ended before the query because the first unpacked four fields from a six-field geometry row and the second retained the old manifest key. Their [first](input_failure_v1.json) and [second](input_failure_v2.json) failure receipts and source versions remain in the directory. The corrected [third query protocol](query_protocol_v3.json) binds the public input and subsequent runs. The checked [Sage runtime receipt](sage-runtime-info.json) was saved before both independent Sage audits.

## Exact rank and N131 transfer decision

The [rank-versus-support analysis](saturation_result.json) compared exact bin sizes to both independently frozen M4RI rank tables. Every bin satisfies `rank = min(|X_(s,t)|,821)`; the aggregate quadratic kernel dimension is **1,674,992**, exactly the finite-support interpolation nullity. A separate streaming Python elimination re-ranked all 1,583,568 rows and all 3,969 bins, reached the same dimension, and found zero bins with extra rank defect. The smallest, median, and largest bin sizes are 128, 392, and 832; the 832-point bin reaches full 821-feature rank. This identifies why the N41 filter works and sets a concrete rejection test for its direct W18 transfer.

The [source-bound W18 projection](transfer_result.json) and [independent integer audit](transfer_audit.json) reject the literal N131 implementation under the 600-second/4-GiB gate:

| Literal N131 W18 resource | Exact requirement from the implemented design |
| --- | ---: |
| Nonzero seed-sum pairs | 68,718,952,449 bins |
| Quadratic coordinate features | 8,516 per bin |
| Fixed-size 16-equation table | 1,178,942,348,215,044 B; at least 274,494-fold compression to fit 4 GiB |
| One bit per distinct-column pair state in one domain | At least 4,306,081,758 B, already 11,114,462 B over 4 GiB |
| Literal two-domain pair-pair loop | At least 1,186,709,766,821,143,716,096 combinations, requiring at least 1,977,849,611,368,572,861/s in 600 s |

The pair-state count is a lower bound from the audited W18 first-pair frontier. The filter-table size and pair-pair work apply to this literal fixed-bin implementation; a symbolic representation would have a different cost. The existing uniform-target bound also requires **286,174,705,817,677,085** target-independent fixed first-two-pair prefixes before the two-free-pair support bound permits 50% success. The target enters this N41 search only after those first two pairs are chosen. These resource and work gates prevent promotion of this implementation to an ordinary N131 query.

The next design step is a compact **joint constraint on at least four still-free pair outputs**. Its N41 control should carry each pair's exact seed-conditioned membership through a balanced S3 sum to the public point, reject partial output families before leaf choices, and report rank against the same `min(rows, features)` interpolation check. Promotion requires a source-bound W18 memory/work projection below 4 GiB/600 seconds and an independently replayed public-only planted control before the frozen ordinary N131 point is queried.
