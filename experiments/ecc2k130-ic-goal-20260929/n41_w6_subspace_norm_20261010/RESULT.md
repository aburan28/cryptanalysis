# Compact seed-sum subspace norm for the N41 S3 link

A seed-sum bucket of W6 same-rotation pair outputs has an exact **six-coefficient binary-linearized representation** before factor-base filtering. Combined with a quadratic resultant, it tests whether an upper S3 link can meet that whole algebraic bucket using a fixed number of field operations per bucket, rather than iterating through its 32 seed-product values. On the frozen N41 residual controls, this one-sided screen found the single positive bucket pair and rejected the negative residual. The positive hit has an independently verified group lift.

For source masks `a,b` with `s=a+b`, write `w_a=Σa_i w_i`, `u_a=Σa_i u_i`, `u_i²+u_i=w_i`, and `A(z)=z²+z`. The transformed coordinate `z=1/(x(P_a+P_b)+1)` satisfies

`z²=u_s²+A(z)p`, where `p=w_a w_b=w_a²+w_s w_a`.

The map `a ↦ p` is binary linear with kernel `{0,s}`, so its image `V_s` has dimension five. Its subspace polynomial

`S_s(X)=∏_{p∈V_s}(X+p)=Σ_{i=0}^5 c_i X^(2^i)`

has six field coefficients. Starting with `S_{0}(X)=X`, adjoining an independent vector `v` updates it by `S_{V+⟨v⟩}(X)=S_V(X)²+S_V(v)S_V(X)`. This represents all 32 source-mask products in the bucket. The unfiltered pair-output condition is `S_s((z²+u_s²)/A(z))=0` when `A(z)≠0`; exceptional coordinates require separate handling.

For a fixed left transformed output `a` and target preimage `t`, the S3 equation is `f(B)=(1+C)B²+CB+D=0`, where `C=A(a)A(t)` and `D=(a+t)²`. A right-bucket product `p∈V_s` gives `g_p(B)=(1+p)B²+pB+u_s²=0`. Eliminating `B` yields a quadratic `H(p)`; with `α=1+C`, `L=p+C`, and `M=(1+p)D+αu_s²`, it is `H(p)=αM²+CML+DL²`. For `α≠0`, `H(p)=0` is equivalent to the resultant of `f` and `g_p` vanishing. The implementation handles `α=0` through the resulting linear equation. To test all `p∈V_s`, it reduces `S_s(X)` modulo `H(X)` and evaluates a quadratic norm. The coefficient recurrence requires six Frobenius steps, independent of the bucket's 32 products. An algebraic hit is checked against the actual usable pair outputs and the elliptic-curve group law.

The [frozen v3 protocol](protocol_v3.json) fixes `GF(2^41)` with modulus `t^41+t^3+1`, `y²+xy=x³+1`, subgroup order `549756390943`, the N41 W6 rotations 20 and 30, the two prior residual points, one worker, 300-second cap per residual, and a 4-GiB RSS cap. The source factor base has **B=256 actual usable projected points** and **K=26 folded columns**. Each residual is a projected point, so the [producer](run.py) checks all four raw preimages under multiplication by four. It enumerates exact left pair outputs while the right bucket uses the compact representation. The candidate ID remains null because this is an S3 stage diagnostic, not a complete IC method.

| Frozen N41 result | Positive residual | Negative residual |
| --- | ---: | ---: |
| Left-output/right-bucket checks across four preimages | 246,456 | 246,456 |
| Algebraic subspace hits | **1** | **0** |
| Hits with an exact right output | **1** | 0 |
| Screen interval | 77.772 s | 76.814 s |
| Status | `COMPLETE` | `COMPLETE` |

The one hit uses left seed sum 16, right seed sum 5, and target preimage 3. The [run receipt](result.json) records the raw output coordinates, exact right match, source/protocol hashes, setup time, and 22,462,464-byte peak RSS. The screen interval starts after target-preimage construction and excludes reusable source/bucket setup; it is **not** a complete single-target IC online interval. CPU wall times are exploratory on this unisolated host. The prior exact-root [bucket norm control](../n41_seed_sum_s3_bucket_norm_20261010/result.json) made the same positive/negative decisions using a different representation and accounting boundary, so these intervals do not establish a speedup.

The [independent checked-Sage audit](sage_audit.json) verified 128 raw source lifts against their fourfold projections, all 978 distinct right pair outputs against the 32-product polynomial in their seed-sum bucket, the positive elliptic-curve group lift, and 252 independent polynomial-GCD checks for the selected left output. Its [runtime receipt](sage_runtime_info.json) identifies the accepted Sage build. The failed [v1](failure_v1.json) and [v2](failure_v2.json) preflight receipts preserve the coordinate mistakes: projected outputs cannot be inserted directly into the source-coordinate identity, and the subgroup inverse of four does not select the raw source lift when cofactor torsion is present.

The same subspace construction gives 14 stored coefficients for a W14 seed-sum bucket on the exact degree-131 field, where the image dimension is 13. The measured N41 method still enumerates left pair outputs and every seed-sum bucket. The next gate is a **double-sided target-conditioned elimination**: form the right-bucket resultant as a polynomial in the left transformed coordinate, reduce it against the left subspace polynomial, and measure exact-hit and false-hit counts on the frozen N41 residuals before attempting an N131 ordinary query.
