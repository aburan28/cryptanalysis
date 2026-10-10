# Split-root norm is the better measured N41 bucket kernel

The exact product-of-roots norm completed every matched N41 seed-bucket
query faster than the quadratic-quotient BSGS norm in an interleaved
same-source panel. Both kernels returned the same GCD roots on the frozen
public-point residual, and their norm polynomials satisfied the exact
resultant congruence modulo the left bucket polynomial. This selects the
split-root form for the next N41 seed-bucket experiment; the degree-131
arithmetic boundary still needs a direct measured comparison.

The [previous complete N41 bucket study](../n41_seed_sum_s3_bucket_norm_20261010/RESULT.md)
already used a product-of-roots norm and batched all left seed buckets into
63 GCD calls per residual. The [quadratic-quotient experiment](../n41_seed_bucket_resultant_20261010/RESULT.md)
gave a second exact representation and a baby-step/giant-step operation
count for one bucket. This panel compares those two norm constructions on
the **same** right and left root sets, with the same target residual and
root-extraction boundary. It corrects the method choice before promoting
an N131 kernel.

## Frozen comparison

The curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, subgroup order
`549756390943`. The W6 four-pair control has actual base `B=256`, 26
signed-Frobenius columns, and public target
`Q=(1458168294740,1672312028033)`. The first four source points are
the archived prefix; the residual is
`(332635421840,2054854538524)`. Seed buckets `(16,5)` and `(1,1)`
were frozen before this panel. Each run starts after the two exact bucket
polynomials and source-root sets have been constructed. Its interval covers
target-dependent norm construction, GCD, and root extraction. The
[protocol](protocol.json) fixes the source hashes, input law, one worker,
method order, 120-second total cap, and 4-GiB RSS cap.

For right roots `b`, the split-root kernel forms

`D(X) = product_b S3(X,b,q) mod L(X)`

and computes `gcd(L,D)`. The BSGS kernel reduces the right root polynomial
through the quadratic S3 quotient and computes its norm `N`. For each
case the producer checked the full polynomial identity

`D = ((X+q)^2)^deg(R) * N mod L`.

| Seed buckets | Split-root query 1 / 2 | BSGS query 1 / 2 | GCD roots | Exact group decision |
| --- | ---: | ---: | --- | --- |
| `(1,1)` | 24.272 / 23.534 ms | 196.337 / 177.196 ms | none | empty direct census |
| `(16,5)` | 29.295 / 26.597 ms | 163.866 / 166.027 ms | `1873642659754` | one verified public row |

The [run receipt](result.json) retains each raw nanosecond interval,
polynomial degree, exact root, operation count for BSGS, setup interval,
complete wall, and peak RSS. The [verifier](verify.py) binds those decisions
to the earlier [independent checked-Sage group audit](../n41_seed_bucket_resultant_20261010/audit.json).
The producer used the repository [checked Sage runtime](sage_runtime_info.json).
This host has no isolation receipt, so these CPU figures are algorithmic
diagnostics. The algebraic identity and root agreement are exact.

## Consequence for the ECC2K-130 gate

The exact degree-131 W14 `s=t` raw pair-output bucket contains 4,124
distinct coordinates per rotation. The prior BSGS projection counts 407
modular polynomial products for one bucket, but that count omits its
coefficient-block accumulation and cannot establish a query-time gain over
the balanced split-root product. The next arithmetic control should run
both kernels on that **same** exact N131 bucket, with all source-root
construction and memory charged separately and a bounded positive and
negative output. A challenge-width public relation then additionally
requires a target-guided generator that narrows early seed families while
at least four pair blocks remain free. This N41 fixed-prefix panel is
proposal `Q20261010045500`, with `candidate_id: null`.
