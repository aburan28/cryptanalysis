# Exact W14 diagonal-atom pair inverse on ECC2K-130

The reciprocal-coordinate diagonal-atom pair has a **131-by-41 exact joint inverse** on the degree-131 challenge field. On a frozen panel, it recovered the unique distinct-mask pair for all 32 constructed pair outputs and rejected all 32 independently drawn trace-zero field controls at full rank 41. An independent checked-Sage replay verified every binary rank decision, recovered seed sum and product, raw elliptic-curve pair sum, and fourfold subgroup projection. This supplies an exact pair-output checker for a target-guided diagonal-atom relation search.

Let `P_a` be a rational W14 raw source point with `x(P_a)=1+1/u_a`, `w_a=u_a²+u_a`, and let `φ` be coordinate-squaring Frobenius. Define the raw diagonal atom `D_a=P_a+φ(P_a)`. The prior diagonal-atom identity gives `x(D_a)=1/w_a`, so its reciprocal leaf coordinate is exactly `w_a`. For two atoms with masks `a,b`, put `s=a+b`, `p=w_a w_b=w_a²+w_s w_a`, and let `z=1/x(D_a±D_b)`. The cleared S3 equation becomes

`s²+z²+zp+(zp)²=0`.

With polynomial W14 basis `w_i=t^i`, `1≤i≤14`, the 14 possible `s²` columns are `t^(2i)` and the 27-dimensional product span is `t²,...,t²⁸`. For a proposed nonzero `z`, the [inverse](pair_inverse.py) solves a binary system with columns `t^(2i)` and `z t^d+z² t^(2d)` for `2≤d≤28`, against `z²`. A full-rank consistent solve determines `s` and `p`; the fixed-sum map `w_a↦w_a²+w_s w_a` has kernel `{0,s}` and recovers the unordered masks. The checker filters audited rational support and folded-column collisions, then verifies the actual group-output coordinate for both relative signs. A rank-deficient query has an exhaustive fixed-sum fallback; the frozen panel did not need it.

The [protocol](protocol.json) fixes `GF(2)[t]/(t^131+t^13+t²+t+1)`, `y²+xy=x³+1`, prime subgroup order `680564733841876926932320129493409985129`, the exact W14 support and source digests, one worker, a 120-second panel cap, and a 4-GiB RSS ceiling. The exact curve ID is `EC1N131Ckb1heb5f1998f20b`. The [input panel](inputs.json) fixes 32 distinct-column source-mask pairs with independent relative sign choices and 32 trace-zero uniform field elements generated as `v²+v`. All controls face the same structural trace condition as a pair output; a trace-one rejection would be a weaker check. Constructed positives test inversion correctness, while the uniform controls test the span filter's selectivity. The candidate ID remains null because target-conditioned relation generation and the rest of the IC pipeline are not specified by this inverse.

| Exact degree-131 panel | Result |
| --- | ---: |
| Full joint rank | **64 of 64** |
| Constructed pair outputs uniquely recovered | **32 of 32** |
| Uniform trace-zero outputs rejected by span | **32 of 32** |
| Positive median / maximum query | 22.146 / 230.718 ms |
| Control median / maximum query | 0.439 / 51.731 ms |
| Complete panel query wall / setup | 1.813 / 0.067 s |
| Peak process RSS | 23,871,488 B |

The [run receipt](result.json) retains each result, rank, recovered mask pair, and query interval. Its CPU timings are exploratory on an unisolated host. The [checked-Sage audit](sage_audit.json), using the saved [runtime receipt](sage_runtime_info.json), independently checked all 32 positive group sums and all 32 trace-zero span rejections. It found 20 raw pair sums already in the prime subgroup and 12 carrying the order-two cofactor class. The first audit required every **raw** sum to have prime order and failed at its second positive case; its [source](sage_audit_v1.py) and [failure receipt](sage_audit_failure_v1.json) are retained. The corrected audit verifies that multiplication by four places every checked atom and pair sum in the prime subgroup.

This cofactor distinction does not change the projected factor-base construction: `4D_a=(1+φ)(4P_a)`. On the odd-order prime subgroup, `1+φ` is invertible. Indeed, a nonzero kernel point would have `φP=-P`, while `φ²+φ+2=0` would then give `2P=0`, impossible in this subgroup. It commutes with Frobenius and sign, so it preserves the audited source base counts and folded columns. The audited W14 support therefore maps to **16,440 distinct subgroup-usable projected points per rotation** before folding and **8,160 folded columns**; the five same-rotation pair policy has **B=82,200** distinct projected points. Raw relation equations must keep the target's four preimages and verify the final fourfold projection.

The next gate is to generate pair-output proposals from the upper target-conditioned S3 chain, apply this 41-column inverse before mask expansion, and measure verified ordinary relation yield and novel rank on a frozen public point. The N41 diagonal-atom indexed relation and sparse circuit provide the full-row correctness control; the degree-131 work needs an unpinned ordinary target decomposition inside its frozen resource envelope before factor logs and single-target timing can be promoted.
