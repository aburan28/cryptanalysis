# Exact N131 two-bucket eliminant fits the local resource gate

A projective linearized norm now intersects two **complete W15 algebraic
pair-output buckets** through a supplied four-atom residual without
enumerating their `2^14 × 2^14` product combinations. On the exact
degree-131 curve, the frozen constructed-positive residual produced a
degree-one intersection containing the independently archived raw pair
output; the separate field control produced degree zero. The positive
native interval was **68.448 s** and the negative interval **83.564 s**,
with **287 MB or less** native peak RSS, one worker, and a 600 s / 4 GiB
cap. A second bounded producer saved both modular remainders, and a
separate parser verified the positive root, S3 link, both GCD degrees,
and a multiplicative inverse proving the negative remainder is a unit
modulo the left bucket polynomial.

This is an exact target-conditioned **block-residual predicate** on
`EC1N131Ckb1heb5f1998f20b`, not a complete public-target query. The field
is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is `y²+xy=x³+1`.
The W15 source is `span(t,…,t¹⁵)`, the common mask-XOR seed is `13686`,
and the two pair rotations are `26,39`. The positive residual is
`1072442453979696659264084726754206488845`, the already audited raw
four-atom output from the [constructed twelve-leaf control](../n131_w15_joint_block_resultant_20261010/RESULT.md).
The negative residual is `t+1`, encoded as `3`. All source masks and
their group sum in the positive bucket intersection were independently
replayed in the [one-sided join audit](../n131_w15_sparse_pair_bucket_join_20261010/RESULT.md):
left `[5576,8382]`, right `[3,13685]`. This experiment fixes the seed and
residual, but leaves both pair products and output coordinates unpinned.
It therefore retains `target_count: 0` and `candidate_id: null`.

## Projective eliminant

Let `c,d` be reciprocal x coordinates of the two pair outputs and `r`
the supplied block residual. Their upper S3 equation is

```text
U(c,d,r) = αd² + βd + γ = 0,
α = 1+c²r² = (1+cr)²,   β = cr,   γ = (c+r)².
```

For a fixed right-bucket seed `s`, source products form the 14-dimensional
linear space `V_s={w²+sw:w∈W15}`. A product `p` gives the pair equation
`g_p(d)=d²+s²+(pd)²+pd`. In the polynomial ring modulo the exact left
bucket polynomial `F_L(c)`, this run checks `gcd(F_L,α)=1`. Thus `α` is a
unit at every left-bucket root. Set `z=αd` and multiply `U` by `α`:

```text
z² + βz + αγ = 0.
```

This monic quadratic removes the dense inverse of `α` that dominated the
first quotient implementation. Its projectively scaled pair factor is

```text
α² g_p(z/α) = (1+p²)z² + pαz + s²α².
```

The `p`-dependent part is linear over `F₂`. The [direct producer](resultant_direct.cpp)
evaluates the same 14-step linearized norm recurrence used by the
[native bucket polynomial](../n131_w15_bucket_norm_native_20261010/RESULT.md),
reducing every power of `z` with `z²=βz+αγ`. It obtains `A(c)+B(c)z`.
The quadratic norm

```text
N(c) = A(c)² + A(c)B(c)β + B(c)²αγ
```

is an exact resultant up to powers of the unit `α`; its degree was
**131,072** in both N131 cases. Computing `gcd(F_L,N)` detects compatible
algebraic output coordinates. A surviving coordinate still requires
field-branch, source-column, and group replay; the archived positive
witness supplies those checks. A zero-degree GCD rejects the whole
algebraic bucket pair.

## Frozen controls and complete measured stages

The [N41 protocol](protocol_n41_resultant.json) first fixed the public
relation's seed-two bucket pair and positive/negative residuals. The direct
resultant reproduced the archived degree-one/degree-zero decisions; the
projective quotient and initial inverse-based quotient gave the same
decisions. The N41 direct positive and negative intervals were 2.019 and
1.953 ms, respectively, under their 120 s / 4 GiB controls. These local
wall observations are exploratory because the host has no CPU-isolation
receipt; their exact intersection degrees agree across three algebraic
forms.

| N131 fixed-seed block residual | Direct resultant | Remainder-certificate producer | Independently checked decision |
| --- | ---: | ---: | --- |
| Constructed positive | 68.448 s, 282,836,992 B RSS | 88.451 s, 286,326,784 B RSS | Degree 1; known left root and S3 link |
| `t+1` negative | 83.564 s, 286,720,000 B RSS | 87.878 s, 269,008,896 B RSS | Degree 0; remainder invertible modulo `F_L` |

All four N131 producer runs used one worker and completed below the frozen
600 s / 4 GiB gate. The [positive](certificate_positive.remainder.bin) and
[negative](certificate_negative.remainder.bin) remainder certificates are
each 557,056 bytes: all 32,768 coefficient slots in declared 17-byte
polynomial-basis encoding. The [separate verifier](verify_certificate.cpp)
reads them independently of the producer and verifies the two GCDs, the
known source output, its S3 equation, and `remainder × inverse ≡ 1 mod F_L`
for the negative case. Its [receipt](verify_result.json) records **41.977 s**
and **64,110,592 B** native peak RSS. The [terminal audit](terminal_result.json)
checks input and binary hashes, frozen protocols, all exact decisions,
resource caps, and preserved stopped attempts. The native runtimes are
stage diagnostics on an unisolated host; they are not single-target IC
online times or controlled CPU speedups.

The inverse-based quotient used a dense `α⁻¹ mod F_L`. Its N131 run reached
round four at 170.943 s and was [stopped with its partial rounds
retained](operator_stop_audit.json); it has no intersection decision. The
first checked-Sage certificate audit was stopped after its slow bit-list
decoder, and the second after decoding the positive remainder but before
its generic degree-32,768 GCD finished. Both [versioned](audit_v1_stop.json)
[stops](audit_v2_stop.json), raw logs, source snapshots, and checked Sage
runtime are retained. The bounded independent NTL remainder checker
completed the exact certificate replay.

## Public-target selection gate

The result moves the *one fixed-seed* algebraic bucket intersection under
the N131 memory and wall gate. It does not make a broad seed sweep viable.
There are 32,767 nonzero W15 seeds for one block, and the eight-offset
two-block policy admits **262,129 ordered nonzero seed pairs**. This
implementation performs 2,030 polynomial ring operations per fixed-seed
residual and took 68–84 s on the two controls. A 600-second one-target
budget could afford only a handful of such calls after other target work;
scanning the seed range would miss that budget by orders of magnitude.
The earlier [one-sided Artin–Schreier join](../n131_w15_sparse_pair_bucket_join_20261010/RESULT.md)
is also faster for one *fixed, source-supported* seed and residual. The
projective eliminant is useful when a joint solver can keep pair outputs
symbolic and use the public target to reject seed families before invoking
the terminal predicate.

The next experiment should couple the published point, both constrained
four-atom blocks, and at least one free pair **before** seed selection.
Freeze all generated seed and residual candidates, count complete failed
attempts and exact bucket rejections, and first recover an unpinned N41
public-point relation without a materialized four-point index. Promote a
new N131 published-point run only after a source-bound one-worker projection
covers all target-dependent stages within 600 s and 4 GiB. Verified
ordinary relation yield, novel rank, factor-base logs, fresh target
recovery, and same-point rho timing remain the full IC pipeline gates.
