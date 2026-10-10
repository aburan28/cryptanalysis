# Full conditional-affine rank for the N41 public-query residual domain

**A 2,021-row exact witness has full rank in a 1,072-dimensional space of
target-branch- and pair-label-conditioned affine residual-coordinate
features.** This proves that this feature family has no universal equality
that can reject a whole family of W8 two-pair backward residuals. The result
holds independently for the x and phi coordinates, and a second implementation
obtained the same ranks on all 99,456 labeled residuals.

## Exact domain and feature map

The input is the independently audited [two-pair backward table](../n41_w8_two_pair_backward_20261009/RESULT.md)
for public `Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`, with subgroup order `549756390943`.
The field is `GF(2)[t]/(t^41+t^3+1)`. The six-block W8 policy has 960 actual
subgroup-usable factor-base points and 77 folded columns. For each of four
raw preimages `T` with `4T=Q`, and each disjoint signed pair of final block
states `P4,P5`, the table stores `R=T-P4-P5`, its branch, and its two state
indices. There are 24,864 valid two-block choices per branch and 99,456
distinct residual group points overall. The saved phi coordinate is
`phi(R)=1/(x(R)+1)`; the source table and phi file already have independent
Sage audits.

The 20-bit label `l` packs two branch bits, seven varying bits from each
canonical pair mask (their fixed-zero bit 5 is removed), and four leaf-sign
bits. Let `L(l)` be the 211 squarefree monomials of label degree at most two.
For the 41-bit coordinate `z`, the evaluated feature vector is

`M(l,z) = (L(l), z_0,...,z_40, z_0*l_0,...,z_40*l_19)`.

It has `211+41+41*20=1,072` columns. Thus a null vector would be an identity
of the exact form

`q(l) + sum_i (u_i + sum_j v_ij*l_j)*z_i = 0`,

where `q` has label degree at most two. Both [native_rank.cpp](native_rank.cpp)
and [independent_rank.py](independent_rank.py) implement this column order.

## Exact rank certificate

| Evaluation matrix | Rows used by independent witness | Rank | Columns |
| --- | ---: | ---: | ---: |
| Label monomials `L(l)` | 211 | 211 | 211 |
| `M(l,x(R))` | 1,072 | 1,072 | 1,072 |
| `M(l,phi(R))` | 1,072 | 1,072 | 1,072 |

The independent witness search processed 2,021 branch-interleaved rows in
the frozen order in [independent_rank.py](independent_rank.py). It saved the
indices of each independent row in
[labels_witness.bin](labels_witness.bin), [x_witness.bin](x_witness.bin), and
[phi_witness.bin](phi_witness.bin). The [rank receipt](independent_rank.json)
binds those files and the source/input hashes. Because these square witness
submatrices have full rank, the complete domain has full column rank;
therefore every coefficient in the displayed identity is zero. The
[all-row M4RI result](result.json) separately found ranks `211/211`,
`1072/1072`, and `1072/1072`. The [label audit](audit.json) independently
reconstructed every one of the 99,456 packed labels from the frozen geometry.

The [protocol](protocol.json) fixes the source and input hashes, the 300-second
and 4-GiB structural-stage caps, and the feature order. Proposal
`Q20261009185000` has `candidate_id: null`: this measures a point-decomposition
constraint family, rather than a complete IC pipeline. The checked
[Sage runtime receipt](sage_runtime_info.json) was saved before the measured
run. The structural run spent 0.243 seconds building labels and 1.808 seconds
in the full-domain native rank stage, 2.051 seconds combined, with
123,256,832 bytes peak RSS. The independent witness search used 0.759
seconds. These CPU times are local diagnostics; the rank statements are exact.

## Next constraint gate

A single residual coordinate, even conditioned on branch, both pair masks,
and all four signs through this feature degree, supplies no equality for
early family rejection. The next test should keep **two still-free pair
outputs jointly** and apply the exact seed-sum inverse while the target
constrains their combined sum. On the same frozen N41 public query, measure
families rejected before leaf enumeration, ordinary relation yield, and
charged solver time; promote to N131 only if that measured rate supports
the one-worker 600-second/4-GiB gate.
