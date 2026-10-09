# One joint linear solve recovers the N131 d13 pair seed sum

**A proposed same-rotation d13 pair output now reaches an exact pair
decision without scanning 8,191 seed sums on the full-rank branch.** The
joint 131-by-104 binary system recovered the seed sum of all 32 saved pair
outputs, rejected all 32 uniform field controls at its span gate, and
matched the earlier exact full-sum inverse on every frozen input. Six
constructed rank-drop outputs took an exact full-sum fallback. An independent
Sage audit reproduced the ranks, recovered seed sums, and 32 signed curve
additions.

Let `V` be the frozen 13-dimensional phi-coordinate source space, let
`a,b∈V`, `s=a+b`, `z=phi(P_a±P_b)`, and `A(t)=t²+t`. The exact S3 identity used
by the [fixed-sum inverse](../n131_d13_same_rotation_pairs_20261009/RESULT.md)
is

`z² = s² + A(z) A(a)A(b)`.

The 13 columns for `s²` span `V²`. The 91 products
`A(v_i)A(v_j)` for `i≤j` span every possible `A(a)A(b)`; on this exact d13
geometry all 91 are independent. For each proposed nonexceptional `z`, the
joint gate concatenates the 13 square columns with the 91 product columns
multiplied by `A(z)`. When this 104-column matrix has full rank, a
consistent solve determines **one** seed-sum code from its first 13
coefficients. The cached rank-12 fixed-sum inverse then recovers and checks
the leaf pair. An inconsistent solve rejects the output. If the joint
matrix loses rank, the implementation charges and runs the complete
linear-batched sum scan. This fallback preserves exact output sets even
when the seed sum is not unique in the relaxed first gate. The two
`A(z)=0` coordinates follow the source inverse's exceptional empty-set
convention.

The [frozen protocol](protocol.json) binds the original audited d13
factor-base geometry, source pivot index, both earlier inverse variants,
checked-Sage runtime, source hashes, 32 saved positive outputs, 32 seeded
uniform controls, six algebraically constructed rank-drop outputs, and two
exceptional coordinates. Both methods handled the same 72 inputs twice
with alternating order. Each query interval contains the complete inverse,
including fallback work; the 91-column product basis and eight-check
comparison index were prepared before timing. The [run receipt](result.json)
retains all 288 timed calls and full pair sets. The
[independent audit](audit.json) used Sage GF(2) matrices for all 70
nonexceptional ranks and independently replayed every accepted group sum.

| Frozen input class | Inputs | Joint outcomes | Joint median query | Eight-check scan median | Paired scan/joint median |
| --- | ---: | --- | ---: | ---: | ---: |
| Exact pair outputs | 32 | 32 pairs, rank 104 | 1.386 ms | 4.322 ms | 2.891× |
| Uniform field controls | 32 | 32 span rejects, rank 104 | 1.322 ms | 4.068 ms | 2.999× |
| Constructed rank drops | 6 | Six rank-103 fallbacks | 9.622 ms | 4.782 ms | 0.511× |
| Exceptional coordinates | 2 | Source empty-set branch | 0.0068 ms | 0.0072 ms | 2.031× |

Across all 144 paired calls, the exploratory paired median ratio was
2.940×; its 10th–90th percentile was 1.412–3.819×. Joint preparation took
1.662 seconds, including construction of the comparison method's parity
checks. Peak process RSS was 48,611,328 bytes. The host has no CPU
isolation receipt, so these wall ratios remain stage diagnostics. Exact
operation counts on the full-rank branch are 91 output-dependent field
products to build the scaled product columns, a 104-column binary solve,
and one fixed-sum pair check on consistent nonzero-sum outputs. The
rank-drop fallback is included in every recorded cost.

The construction extends the earlier [W18 division-free pair oracle](../N131_W18_LINEAR_PAIR_ORACLE_RESULT.md)
to this d13 same-rotation policy and extracts the seed sum directly from
the first linear system. The dynamic matrix can have full rank even though
the complete d13 pair-output set has [full affine span](../n131_d13_pair_output_linear_span_20261009/RESULT.md):
the scaled product columns change with `z`.

The next experiment is a public-target joint solver that **generates**
compatible outputs for two or more pair domains before fixing their leaves.
This inverse makes a proposed output cheaper to check, but the frozen
N131 relation gate still requires target-dependent cross-pair pruning,
an unpinned N41 relation, and a credible 600-second/4-GiB N131 projection.
This is proposal `Q20261009233000`; its complete-pipeline candidate and
run IDs remain null.
