# Decomposition above the linearization limit: search record and problem statement

This is the working record for the goal "find a genuinely new point-decomposition method for
binary-curve index calculus that stays cheap well above the linearization limit".
Setting: m = 2, an F_2-subspace factor base V of dimension l in F_(2^n), n prime, curve
`y^2 + xy = x^3 + b`. The linear two-point oracle (Courtois 2016; `../linearized-half-decomposition`;
`PDP2ht` here) costs `2^d * poly(n)` per query. Here `d = max(0, l + dim V^(2) - n - 1 + [V in ker Tr])`,
which is `3l - n - 2` for progressions. "Cheap well above the limit" means polynomial, or at least
much less than `2^d`, for `l` clearly above `(n + 2)/3`.

## 1. Literature and in-repository search (done 2026-10-05)

| Approach | Source | Regime and cost | Beats `2^d` above the limit? |
|---|---|---|---|
| Gröbner / F4 / F5 on the Weil descent of S_3 | Faugère-Perret-Petit-Renault 2012; Petit-Quisquater 2012; Shantz-Teske 2013 | The degree of regularity grows with n: 3, 3, 4, 4, 4, 4, >= 5 at n = 12 ... 40 with `l = n/2` (Kosters-Yeo 2015 slides; Huang-Kosters-Yeo 2015) | No. At `n = 40, l = 20` (d = 18) the Macaulay matrices at degree >= 5 are far larger than `2^18` |
| First fall degree 2 from the trace morphism | Kosters-Yeo 2015 | Explains the low first fall degree, not the solving degree | No |
| Splitting S_(m+1) into S_3 chains with auxiliary variables | Semaev 2015; Karabina 2015; Galbraith-Gaudry 2016 survey ("unrolling the resultant") | Claimed `2^(c sqrt(n ln n))` under a first-fall-degree assumption that later work doubts | No supported claim |
| Half-trace linearization and a GCD guess | Courtois 2016 | Splitting in two and three in `2^(n/3) poly` | Matches the limit; the GCD guess is a structured enumeration |
| SAT / XOR-SAT (WDSat), symmetry breaking, vertex-cover preprocessing | Trimoska-Ionica-Dequen 2019, 2020 | m = 2 worst case `2^(l)` (minimum vertex cover = one block); m = 3 up to `l = 11, n = 89` in days | No: `2^l > 2^d` for every `l < (n+2)/2` |
| Overdetermined bilinear solvers (y-XL, y-MXL, y-HXL) | "On the complexity of solving generic overdetermined bilinear systems" (AMC 2021, arXiv 2006.09442); Faugère-Safey El Din-Spaenlehauer 2011 | Degree about `ceil(n_x (n_y - 1)/(m - n_x)) + 1` | Not on generic counts for our residual system (Sec. 3) |
| Hybrid exhaustive search plus Macaulay (BooleanSolve) | Bardet-Faugère-Salvy-Spaenlehauer 2013 | `2^((1 - 0.208 alpha) N)` for `m = alpha N` | No: about `2^(0.58 (l + d))` here, against `2^d` |
| Non-subspace factor bases (`L(x) = 0` for compositions of low-degree maps; quasi-subfield polynomials) | Petit-Kosters-Messeng 2016; Huang-Kosters-Petit-Yeo-Yun 2020 | Other bases, solved with Gröbner or resultants | Not as a linear oracle: these bases break the linearization |
| Rho with precomputation | Bernstein-Lange 2012 | `1.77 r^(1/3)` online after `1.24 r^(2/3)` precomputation | Reference point |
| Generic lower bound with preprocessing | Corrigan-Gibbs-Kogan 2018 | `S T^2 = Omega(eps N)` | Reference point (Sec. 2) |
| Structured generic-group model | Corrigan-Gibbs-Henzinger-Wu, ePrint 2026/384 | `T = Omega(min(sqrt(q), 1/delta))` queries to a free structure oracle (`delta` = structured fraction) | Treats the oracle as free, so it does not forbid a cheap oracle above the limit |
| In this repository | `../linearized-half-decomposition` (k-point budget, at least `2^(2n/3)` total); `../pdp-scaling`; `../frobenius-quotient-m4` (nonlinear weight base, m = 4); `../factorbase-census`; `../homogeneous-fraction`; `../hamming-ic-e2e-20260929` | All stay at or above the known exponents | No |

## 2. Why the limit is a real barrier: the generic preprocessing curve

Store the `S = 2^l` factor-base logs as advice. The online time is `T = (1/p_dec) * cost(oracle)`,
with `p_dec ~ 2^(2l - n)` (up to the psi-class constant).

With `r ~ 2^(n - 2)` (cofactor 4):

- Below the limit, `T ~ 2^(n - 2l)`, so `S T^2 / r ~ 2^(n - 3l + 2)`. That is above 1 (IC worse
  than generic) for `l < (n + 2)/3`.
- Above the limit, with the linear oracle, `T ~ 2^(n - 2l) * 2^d = 2^(l - 2)`, so
  `S T^2 / r ~ 2^(3l - n - 2) = 2^d`. That is again above 1, by exactly the residual search.

So with the best known oracle, m = 2 subspace IC **touches the generic `S T^2 = N` trade-off
only at the linearization limit**, `l ~ (n + 2)/3`, and is worse on both sides. The measured
`log2(S T^2 / r)`, with T the predicted `PDP2ht` online cost in group additions, has its minimum
at the limit and rises on both sides:

| n | l = limit - 1 | at the limit | limit + 1 | limit + 2 |
|---|---|---|---|---|
| 19 | 12.8 (l6) | 12.7 (l7) | 13.6 (l8) | 16.7 (l9) |
| 23 | 14.6 (l7) | 12.5 (l8) | 13.0 (l9) | 15.0 (l10) |
| 41 | 13.9 (l14) | 13.1 (l15) | 14.9 (l16) | 17.7 (l17) |

The roughly 13-bit floor is the polynomial per-attempt overhead, in group additions.

A method that stays cheap above the limit, with `T ~ 2^(n - 2l) poly`, would give
`S T^2 / r ~ 2^(n - 3l + 2) poly < 1`, strictly below the generic curve. That is possible in
principle, since IC is not generic, but it would be a non-generic preprocessing advantage for
prime-degree binary curves, which no source above reports. We did not find this
framing of the linearization limit in the sources above.

## 3. The residual problem, exactly

In `(e1, e2) = (x1 + x2, x1 x2) in V x V^(2)`, the S_3 system is F_2-linear. After that linear
solve, what is left above the limit is the following.

Find `t in F_2^d` and `X in V` (l bits) with

    X^2 + u(t) X + p(u(t)) = 0,    u(t) = u0 + sum_k t_k f_k,    p affine in t.

Only the `V^(2)` part of the equation is nontrivial, so this is an **overdetermined bilinear
system**: `2l - 1` equations in `l + d` unknowns, with bilinear terms `t_k x_i (f_k v_i)`.

Generic counting for this shape:

- Linearization needs `(l + 1)(d + 1) - 1 <= 2l - 1`, which fails for `d >= 1`.
- With y = t: degree about `d + 1`, so cost about `l * 2^d`.
- With y = X: degree about `d/2 + 1`, with `C(l, d/2)` columns, which is larger than `2^d` once `l > 4`.
- MinRank in the support-minors model (a `(2l - 1) x (l + 1)` matrix pencil, d variables, corank 1):
  degree about `d/3`, cost about `2^(0.92 omega d)`.

On generic counts, nothing beats enumerating the `2^d` values of `t`. The open question is whether
**our** residual system is generic. It is built from field multiplication, the half-trace and a
progression, so it could be easier. Sec. 4 measures this.

## 4. Candidate 1: exploit the non-generic degree of the residual system (tested; rejected)

`residual.py` builds the residual Boolean system for real targets, one system per consistent
`eps`, and solves it with the MXL degree scan (`--solver mxl`, at most 26 variables) or with y-XL
in t (`--solver yxl`). On 142 targets, the residual is solvable exactly when the target decomposes
(0 mismatches with the half-trace solver). Factor base: geomtraceu, seed 1. The MXL operation
counts below are word operations times the frozen `mac_op` price (302 rps). Data:
`results/residual-n23.jsonl`, `results/residual-n41.jsonl`.

| n | l | d | N = l + d | MXL solving degree, every target | generic overdetermined-bilinear degree | MXL residual cost (rps, median) | `PDP2ht` per failed attempt (rps) |
|---|---|---|---|---|---|---|---|
| 23 | 9 | 3 | 13 | 2-3 | 3 | 3.0e6 | 2.4e7 |
| 23 | 10 | 6 | 17 | 3 | 5-6 | 6.4e7 | 1.7e8 |
| 23 | 11 | 9 | 20 | 3 | 9 | 7.6e8 | 1.2e9 |
| 23 | 12 | 12 | 24 | **4** | 13 | 1.4e12 | (`2^12` candidates, about 6e8) |
| 23 | 13 | 13 | 26 | **4** | 17 | 5.2e12 | — |
| 41 | 15 | 3 | 19 | 2-3 | 3 | 2.7e7 | 3.9e7 |
| 41 | 16 | 6 | 22 | 3 | 5 | 4.7e8 | 2.9e8 |
| 41 | 17 | 9 | 26 | 3 | 7 | 4.6e9 | 2.3e9 |

What this shows:

- **The residual system is far from generic.** Its solving degree is 3 up to `d = 9` and 4 at
  `d = 12-13`, where the generic overdetermined-bilinear prediction is 7-17. This agrees with the
  slow growth of the degree of regularity that Kosters-Yeo report for the full system at
  `l = n/2`: 3, 3, 4, 4, 4, 4, >= 5 for `d = 4 ... 18`.
- **Low degree does not make it cheaper than enumeration.** The ratio of MXL cost to enumeration
  grows with d: 0.12, 0.38, 0.63 at n = 23, and 0.70, 1.6, 2.0 at n = 41. At the step to degree 4
  the Macaulay matrices jump by three orders of magnitude.
- y-XL in t needs t-degree `k + 1 = 4`, about `d/2`, at `d = 9`. That spans half the t-cube
  (4608 columns), and its total work (9.2e7 word operations) exceeds MXL (1.5e7).
- If the degree keeps growing about linearly (roughly `2 + d/6`, as these points and the
  Kosters-Yeo table suggest), Macaulay costs about `C(N, d/6)^omega`, which is exponentially
  worse than `2^d`. Only a degree that grows logarithmically would win. The 26-variable limit of
  the Macaulay layout stops us measuring beyond `d = 13`; a sparse layout would be needed.

**Verdict:** rejected as a cheaper method. The non-generic low degree is a real structural fact
about the residual system, and the measurement is new as far as we know. It does not give a
solver below `2^d` in any measured cell, and the trend points the wrong way.

## 5. Open leads (not yet novelty-checked)

1. **Explain the degree-3 refutations.** Find which degree-3 multiples yield the refutation, and
   turn that mechanism into a direct algorithm without a Macaulay matrix.
2. **Measure the degree trend beyond `d = 13`** with a sparse-layout MXL. This needs a pdpkernel.c
   change, because the layout is a dense `2^N` table.
3. **Other decomposition shapes.** Pairs from two subspaces, cosets, and Frobenius twists were
   checked on paper: each needs more unknowns per pair than one subspace. Candidates that change
   the shape fundamentally (not m = 2 over one subspace) still need a literature check.
