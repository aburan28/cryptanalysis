# Double-sided seed-sum elimination reaches an expanded-polynomial boundary

The N41 double-subspace construction eliminates both unfiltered W6 pair-output families from a target-conditioned S3 link. Its left-family polynomial has degree **4,032**, exactly `63 × 64`. A verified quadratic resultant gives degree-at-most-128 polynomials for each right seed-sum bucket. On the frozen residual controls, polynomial GCD dominated both measured variants: the per-bucket run reached its 180-second cap, and multiplying right-bucket resultants before GCD also reached its cap. The calculation identifies a concrete degree-131 boundary: a literal expanded global-left polynomial for the W14 source has degree **268,419,072** and requires at least **4,395,362,321 bytes** just to store 131-bit coefficients, above the frozen 4-GiB budget before temporary storage.

For each nonzero source-mask sum `s`, let `V_s={w_a²+w_s w_a:a∈GF(2)^6}`. It has 32 elements. With `u_s²+u_s=w_s`, the unfiltered pair-output polynomial in transformed coordinate `Z=1/(x+1)` is

`F_s(Z)=∏_{p∈V_s}((1+p)Z²+pZ+u_s²)`.

Every factor has degree two on the frozen N41 source, so `deg F_s=64`. The product over all 63 left seed sums has degree 4,032. For a fixed target preimage `t` and left coordinate `Z`, put `C=(Z²+Z)(t²+t)` and `D=(Z+t)²`. The upper S3 equation in right coordinate `B` is `f(B)=(1+C)B²+CB+D`. For a right product `p`, set `M=(1+C)u_s²+(1+p)D`, `L=p+C`, and `N=Cu_s²+pD`. Its quadratic resultant is the polynomial `Res_B(f,(1+p)B²+pB+u_s²)=M²+LN`. Multiplying this over the 32 products gives one right-bucket resultant of degree at most 128 in `Z`. The [checked-Sage audit](sage_audit.json) independently verified the identity on all 32 products of the positive witness bucket and checked the positive S3/product root.

The [first frozen protocol](protocol.json) and [batched protocol](batch_protocol.json) use the exact N41 field `GF(2)[t]/(t^41+t³+1)`, curve `y²+xy=x³+1`, subgroup order `549756390943`, rotations 20 and 30, **B=256 actual usable projected base points**, **K=26 folded columns**, and the same known positive and negative residuals as the earlier exact-bucket study. Each query covers all four raw preimages of its projected residual. Both have one worker, 4-GiB RSS ceiling, and a nominal 180-second wall cap per residual. This is a stage proposal with `candidate_id: null` and `target_count: 0`.

| Frozen residual query | Per-bucket GCD | Batched right resultants |
| --- | ---: | ---: |
| Positive work completed | 173 of 252 bucket/preimage checks | 2 of 4 preimages |
| Positive norm build / GCD | 7.492 / 172.526 s | 18.484 / 184.200 s |
| Positive wall / status | 180.025 s / `CENSORED_TIME` | 209.953 s / `CENSORED_TIME` |
| Negative work completed | 86 of 252 bucket/preimage checks | 3 of 4 preimages |
| Negative norm build / GCD | 8.032 / 176.128 s | 17.845 / 256.028 s |
| Negative wall / status | 184.179 s / `CENSORED_TIME` | 280.288 s / `CENSORED_TIME` |
| Target-independent setup | 2.934 s | 1.980 s |
| Peak process RSS | 351,191,040 B | 555,712,512 B |

The [per-bucket receipt](result.json) and [batched receipt](batch_result.json) retain the complete phase costs and partial coverage. The known positive witness uses target preimage 3; neither capped run reached that preimage, so zero observed hits in these partial scans is censored evidence. The batched producer checks its wall cap after a whole preimage, allowing an overrun; its actual walls above are preserved and are not treated as cap-compliant timings. All CPU timing here is exploratory on an unisolated host. The earlier [exact-root batched norm](../n41_seed_sum_s3_bucket_norm_20261010/RESULT.md) completes these residual decisions with 63 GCDs on the projected-coordinate domains; its query boundary differs from the four-preimage source-coordinate experiment here.

For the exact degree-131 W14 polynomial source, `w_i=t^i` for `1≤i≤14`. Every `w_a w_b` has degrees only 2 through 28, below the field modulus degree, so `p=1` is absent from each seed-product image. Each unfiltered bucket polynomial therefore has degree `2^14=16,384`, and the product of all `2^14−1=16,383` nonzero seed buckets has degree `268,419,072`. A dense coefficient array needs at least `(268,419,072+1)×131` bits, or 4,395,362,321 bytes. This is a bound for the **expanded global-polynomial representation** under the 4-GiB gate; a factored or linearized representation can be smaller, but would still need a target-guided way to avoid testing every seed sum.

The next experiment should keep the compact fixed-sum subspace polynomials factored and couple seed sums to the target before expansion or a global GCD. It should first demonstrate unpinned N41 public-point relation search and a source-bound N131 operation/RSS gate, then measure an ordinary N131 query. The current expanded-GCD path is retained as a precise control and boundary rather than promoted to the challenge-width solver.
