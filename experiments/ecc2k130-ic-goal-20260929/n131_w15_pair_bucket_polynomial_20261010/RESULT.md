# Sparse output polynomial for one full W15 pair-product bucket

An exact linearized norm represents **all 16,384 products** in one W15
seed bucket by a degree-32,768 pair-output polynomial with only **486
nonzero coefficients**. Its [saved coefficients](polynomial_sparse_v3.json)
vanish at an independently verified raw pair output from the N131
eight-offset control. A separate bit-field implementation evaluated the
saved polynomial and the direct product over all 16,384 products at that
output and three field controls; all four values matched exactly. The
same recurrence equals the direct 32-factor polynomial for an N41 W6
bucket. This is a compact exact constraint on a whole product family,
available for a target-conditioned pair or block join.

## Polynomial identity and scope

Work in `GF(2^n)` on `y²+xy=x³+1`. For a fixed nonzero seed sum `s` in
`W_d=span(t,...,t^d)`, let

```text
V_s = {w²+sw : w in W_d},                  dim V_s = d-1
A(x) = x²+x
g_p(c) = c²+s²+A(cp)
F_s(c) = product over p in V_s of g_p(c).
```

For the reciprocal coordinate `c=1/x(P_a+P_b)` of a raw pair with
source coordinates `w_a,w_b` and `s=w_a+w_b`, its S3 equation is
`g_{w_aw_b}(c)=0`. Thus every such pair output is a root of `F_s`.
The polynomial covers the **complete algebraic product image** `V_s`;
source rationality, sign choices, and distinct folded columns remain
separate exact checks.

For a binary basis of `V_s`, write `v_i(c)=A(cp_i)`. Start with
`L_0(Y)=Y`. Adjoining each basis vector uses

```text
L_{i+1}(Y) = L_i(Y)² + L_i(v_i(c)) L_i(Y).
```

Induction gives `L_i(Y)=product_{p in span(p_1,...,p_i)}
(Y+A(cp))`; therefore `F_s(c)=L_{d-1}(c²+s²)` exactly. At every
stage `L_i` has only `i+1` Frobenius powers of `Y`, with polynomial
coefficients in `c`. The final degree is at most `2^d`, although the
product represents `2^(d-1)` distinct source products.

## Frozen measurements and replay

The N41 control uses `GF(2)[t]/(t^41+t³+1)`, `d=6`, and seed mask `4`.
Its rank-five product image has 32 elements. The [producer](produce_v3.py)
proved polynomial equality against the product of all 32 explicit factors:
degree **64**, **33** nonzero coefficients.

The N131 control uses `GF(2)[t]/(t^131+t^13+t²+t+1)`, `d=15`, seed
mask `13686`, and the raw pair from the previously
[replayed eight-offset witness](../n131_w15_joint_block_resultant_20261010/restricted_audit_result.json).
The pair was unrotated from Frobenius shift `26` before evaluating the
polynomial. The [v3 protocol](protocol_v3.json) froze the source hashes,
one worker, 150-second parent cap, and 4-GiB sampled-process RSS guard.

| Pair-product bucket stage | N41 W6 | N131 W15 |
| --- | ---: | ---: |
| Product-space dimension / products | 5 / 32 | 14 / 16,384 |
| Output polynomial degree / nonzero coefficients | 64 / 33 | **32,768 / 486** |
| Positive raw pair output | Direct-product identity | Polynomial value zero |
| Fixed field controls | — | Two polynomial values nonzero |
| Producer stage elapsed | 0.19 s | 67.96 s |
| Parent wall / sampled peak RSS, complete v3 run | — | 73.612 s / 2,761,736,192 B |

The [v3 receipt](receipt_v3.json) records process exit `0`, all source
and output digests, wall cap, and sampled RSS. Its N131 stage time
includes polynomial construction, pair-output check, coefficient digest,
and sparse serialization. The parent interval also includes checked-Sage
startup and the N41 control. These CPU observations are stage diagnostics
on an unisolated host, not an IC online or rho comparison.

The [independent audit](audit_result.json) used separate integer
polynomial arithmetic over the degree-131 field. It reconstructed a
rank-14 product basis, enumerated all 16,384 distinct products, and
matched the direct `F_s(c)` product against the saved sparse polynomial
at four fixed coordinates. It also rebuilt the dense coefficient SHA-256
`b2c472e1ce8187de33413c48eee469d1689f7a185b5f7d9932eca2c6ce7d1aad`.
The [terminal audit](terminal_audit.json) binds both successful v2/v3
runs and the independent replay. The initial parent monitor failed before
mathematical output because macOS denied a global process-list call;
its [failure receipt](failure_v1.json) is preserved, and the v2/v3
monitors use direct launched-process RSS queries.

## Target-conditioned continuation

The sparse certificate makes a concrete next experiment possible: for a
supplied residual output, eliminate one pair-output coordinate from its
degree-32,768 bucket polynomial and the upper S3 equation, then intersect
the result with the second seed bucket polynomial **without enumerating
their 268,435,456 product pairs**. Test exact positive and field controls
on N41 first, then the constructed N131 W15 pair blocks under one worker,
600 seconds, and 4 GiB. The public-query method must still leave seeds,
free pairs, and target branches open and pass a complete source-bound
projection before promotion to the frozen N131 public point. This is a
proposal-stage constraint with `candidate_id: null`.
