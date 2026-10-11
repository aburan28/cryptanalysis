# Linearized S3 bucket resultant for exact pair-output families

A fixed left pair-output coordinate and target now constrain a whole right
seed-sum family by **one GF(2) span test**. The test uses at most five
transformed basis vectors for the N41 W6 source and never constructs the
right pair-output polynomial or its pair-state vector. On the frozen N41
field, 126 compact pair-polynomial identities passed exactly, and 1,701
target-dependent bucket decisions agreed with both the 32-factor resultant
and an independent Sage root/S3 replay. The constructed two-pair group
witness hits right seed 5; the sampled left coordinates on each frozen
residual have no right-bucket hit. This establishes an exact component for
target-conditioned pair-block propagation. It does not yet generate the
first pair output from an unpinned four-pair public target.

The [protocol](protocol.json) fixes curve `EC1N41Ckb1h7d5e80d3c4d0`,
`GF(2)[t]/(t^41+t^3+1)`, `y²+xy=x³+1`, W6 rotations 20 and 30, actual
factor-base count **B=256**, folded columns **K=26**, one worker, and a
4-GiB RSS cap. The experiment is proposal `Q20261011201100`; its
`candidate_id` and `run_id` are null. Inputs comprise a constructed raw
two-pair group witness and all four raw lifts of each frozen positive and
negative projected residual. Three left coordinates per raw target are
checked against all 63 nonzero right seed sums. The two residuals are
stage controls and the constructed sum is a correctness witness.

## Exact operator

For one nonzero seed sum `s`, let `V_s` be the image of
`w_a ↦ w_a²+w_s w_a` over the W6 source space. It has dimension five.
Let `u_s²+u_s=w_s`. In the transformed pair-output coordinate `Z`, the
unfiltered bucket polynomial is the homogenized linearized polynomial

`F_s(Z) = (Z²+Z)^32 L_{V_s}((Z²+u_s²)/(Z²+Z))`,

with the polynomial expansion defining the exceptional `Z²+Z=0` cases.
It has only six linearized coefficients before homogenization, versus 32
quadratic factors and degree at most 64 when expanded. The
[producer](run.py) checked this as a full polynomial identity for every
one of the 63 seeds in each of two rotations, not only at sampled roots.

For a fixed left coordinate `z` and target reciprocal `t`, put
`C=(z²+z)(t²+t)`, `D=(z+t)²`, and `α=1+C`. The S3 resultant of the target
link with the right pair factor indexed by product `p∈V_s` is

`q(p)=[αu_s²+(1+p)D]²+(p+C)(Cu_s²+pD)`.

In characteristic two this is `A+Bp+Ep²`, with
`A=(αu_s²+D)²+C²u_s²`, `B=C(u_s²+D)`, and `E=D²+D`. Thus
`W={Bp+Ep²:p∈V_s}` is an additive subspace. If its dimension is `r`,
then the complete 32-factor bucket resultant equals
`L_W(A)^(2^(5-r))`. In particular, the bucket can link to `z,t`
exactly when `A∈W`. Computing the five transformed basis vectors and
testing binary span gives the same zero decision without enumerating
the 32 right products. Every tested transformed image had rank five;
the formula also handles rank loss by its kernel multiplicity.

| Frozen exact control | Left coordinates × raw targets | Right bucket decisions | Bucket hits | Combined producer validation interval |
| --- | ---: | ---: | ---: | ---: |
| Constructed group sum | 3 × 1 | 189 | 1, at right seed 5 | 82.355 ms |
| Frozen positive residual | 3 × 4 | 756 | 0 for these left coordinates | 323.263 ms |
| Frozen negative residual | 3 × 4 | 756 | 0 for these left coordinates | 310.670 ms |

The producer interval includes the span test, linearized polynomial
evaluation, and independent 32-factor product **for each decision**. It
is a correctness-panel interval on an unisolated host, not a stand-alone
kernel timing or an online IC measurement. The [result](result.json)
records all 27 target/left-coordinate cases, all per-case intervals,
the constructed group points, polynomial counts, and 272,220,160-byte
peak process RSS. The [independent audit](audit.json) rebuilt every
right bucket by solving its 32 quadratic factors with an odd-degree
half-trace, compared all 1,701 decisions using the S3 equation, replayed
the constructed point sum, and verified the eight fourfold residual
lifts. Its right-bucket root counts are 19–43 distinct coordinates;
the expanded factors retain multiplicity.

## Degree-131 transfer boundary

For the exact W14 polynomial source, a nonzero seed has a rank-13 product
image: a bucket's unfiltered polynomial has degree at most 16,384 yet its
linearized form needs **14 coefficients**. At a fixed left coordinate and
target, the 8,192-factor right-bucket resultant reduces to at most 13
transformed basis vectors and a 131-row binary span test. This is an
algebraic operation-count reduction for one specified seed; no N131 wall
time is inferred from the N41 panel.

The outstanding N131 work is selecting relevant left coordinates and
seed families from the public target while multiple pair domains remain
free. Testing all `2^14−1` right seeds for every left output would still
be a broad sweep, and the W18 first-pair domain has at least
34,448,654,064 distinct-column states under the frozen policy. The next
experiment should compose this span predicate with an implicit left
bucket and show target-dependent elimination of many seed families in
one operation. It must first recover an unpinned N41 eight-point row
under 120 seconds and 4 GiB, then give source-bound N131 work/RSS
under 600 seconds and 4 GiB before an ordinary N131 run. Relation yield,
novel rank, factor logs, fresh single-target online recovery, and
same-point rho remain the full candidate measurements.
