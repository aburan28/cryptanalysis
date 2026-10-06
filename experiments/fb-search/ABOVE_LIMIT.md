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
| Summation-polynomial evaluation instead of Gröbner bases; `(m - 1)`-subset enumeration plus factor-base lookup | McGuire-Mueller, ePrint 2017/1262; Amadori-Pintore-Sala 2018 | Prime fields; `O(p)` total | No: an enumeration of factor-base subsets, not a solver for the residual |
| NP-completeness of `S_r` zero-testing; first fall degree 2 | Kosters-Yeo, arXiv 1503.08001 | Worst-case hardness under an assumption | No (a limitation, not a method) |
| Frobenius-invariant factor bases for Koblitz curves | ePrint 2020/1315 | Fewer systems to solve (factor `1/n'`), faster linear algebra | No: a constant factor, and the same solvers |
| Web search for 2022-2026 binary-field PDP work (2026-10-06) | ePrint, arXiv | Found only prime-field or unrelated work, such as ePrint 2024/1923, 2025/015, 2026/1299 | Nothing newer than WDSat for prime-degree binary fields |
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

**Graded targets for an above-limit oracle.** Suppose an oracle costs `c(d)` per attempt. Then
`T ~ 2^(n - 2l) c(d)`, so `S T^2 / r ~ 2^(n - 3l + 2) c(d)^2 = c(d)^2 / 2^d`. Three regimes
follow:

- `c = 2^d` is the enumeration.
- Any `c` well below `2^d` meets the goal's "cheap" criterion.
- `c = 2^(d/2)`, a square-root or meet-in-the-middle speed-up, would put above-limit IC exactly
  **on** the generic preprocessing curve.

Only `c < 2^(d/2)` would beat the Corrigan-Gibbs-Kogan curve, and with it Bernstein-Lange at equal
advice. So even a successful birthday-type residual solver would tie with generic rho with
precomputation, not beat it.

**The symmetric linear oracle is optimal among linear subspace-pair oracles.**

- **Setup.** Take subspaces A, B of dimensions a, b, with `k = dim(A ∩ B)`. An oracle that is
  linear in `(x1 + x2, x1 x2)` over `(A + B) x (A B)` is linear only if
  `dim(A + B) + dim(A B) <= n + 1`.
- **Bound.** By Hou-Leung-Xiang (n prime), `dim(A B) >= a + b - 1`. So `2(a + b) - k <= n + 2`.
- **Optimum.** With `k <= (a + b)/2`, the number of pairs covered, `2^(a + b)`, is at most
  `2^(2(n + 2)/3)`. Equality holds only for `A = B`, the symmetric oracle at the limit.
- **Unions of subspaces.** Cross pairs between two progressions `xi_i P`, `xi_j P` have a poly-time
  linear oracle for `l0 <= (n + 1)/4`, but they cost `2^(n - 2 l0) >= 2^(n/2)` per relation,
  against `2^(n/3)` at the symmetric limit.

So nothing linear goes past the limit. An above-limit method has to be genuinely nonlinear, as in
`../linearized-half-decomposition`, which reaches the same conclusion through its k-point budget.

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
- At the time, the n = 23 points suggested roughly linear growth (`2 + d/6`), under which
  Macaulay costs about `C(N, d/6)^omega`, exponentially worse than `2^d`. Sec. 4b measures beyond
  the 26-variable limit and finds slower growth, so that extrapolation is **superseded**.

**Verdict (at the sizes measured):** not cheaper than `2^d` in any cell. The non-generic low degree is a real structural fact
about the residual system, and the measurement is new as far as we know. It does not give a
solver below `2^d` in any measured cell, and the trend points the wrong way.

### 4b. The degree beyond 26 variables (`smxl.c`)

`smxl.c` is a standalone sparse-column MXL closure: 64-bit monomial masks and a sorted column
map, with no `2^N` table. It uses the same closure rule as `macaulay.py` mode `mxl`, and agrees
with it on degree and order of work at `d = 6, 9`. It runs as `residual.py --solver smxl`. Data:
`results/residual-smxl-n41.jsonl`. All targets below are on n = 41, geomtraceu seed 1. For
non-decomposable targets (checked against the half-trace solver), "refuted at D" means 1 is in
the degree-D closure.

| l | d | N | MXL degree that refutes (every target) | columns at that degree | word operations (median) | MXL cost (rps) | `2^d` enumeration (rps, at about 4.4e6 per candidate) | ratio |
|---|---|---|---|---|---|---|---|---|
| 17 | 9 | 26 | 3 | 2952 | 2.7e7 | 8.3e9 | 2.3e9 | 3.6 |
| 18 | 12 | 30 | **4** (3 is not enough: rank 3796 of 4526) | 31931 | 4.2e10 | 1.3e13 | 1.8e10 | 700 |
| 19 | 15 | 34 | 4 | 52956 | 2.2e11 | 6.6e13 | 1.4e11 | 470 |
| 20 | 18 | 38 | 4 | 82993 | 9.3e11 | 2.8e14 | 1.2e12 | 240 |

For decomposable (planted) targets the same degree solves the system. The closure ends with
`N - 1` linear pivots and two standard monomials, the swapped pair `(X, Y)`, at `d = 9` (degree 3),
`d = 12` (degree 4) and `d = 15` (degree 4: 33 linear pivots, rank 52954 of 52956). The other `eps`
branch of a planted target is refuted at the same degree.

Reading:

- At the sizes measured, the degree grows **slower than the linear extrapolation in Sec. 4**: 3 up
  to `d = 9`, then 4 up to at least `d = 18`. `d = 18` is `l = 20` at n = 41, essentially the
  Kosters-Yeo point `n = 40, l = n/2`, where they report an F4 degree of regularity of at least 5.
  Our measure is different: the MXL refutation or solving degree, close to a last fall degree in
  the sense of [HKY15], not the highest degree that F4 processes.
- **MXL is still much costlier than enumeration** in every cell. The ratio falls only while the
  degree stays fixed: 700, 470, 240 across `d = 12, 15, 18`, about 1.5x per 3 dimensions. Parity
  needs roughly 15 more such steps (`d ~ 60`) at degree 4. For n = 131 at `l = n/2` that would
  mean degree <= 4 at `d ~ 62`, with about 1e7 columns.
- Gröbner bases on the descent system are not new [FPPR12, PQ12, KY15]; the residual system is the
  same system with its linear part eliminated. What this adds is the measured refutation/solving
  degree up to `d = 18` and the cost against `2^d`. The open question it isolates: **is the
  solving degree of the m = 2 descent system bounded, or logarithmic, in d?** If it is bounded,
  the m = 2 PDP is polynomial time at every l, which would contradict the expectation in
  [KY15]/[Cou16]. If it grows linearly, Macaulay never wins. Sec. 4c answers
  it at the sizes reachable here: the degree rises to at least 5 by `d = 21`, so the growth is
  about linear.

## 4c. Candidate 2: one-block mutant closure on the residual system (tested; rejected)

**Method.** Multiply only by the residual variables t (`smxl.c`, `smxl_run_restricted`) and keep
only columns of X-degree <= 1. That is exactly the set of monomials the t-closure can reach,
because every equation is linear in X. Then read the linear relations in t off the closure and
split each surviving candidate by one half-trace, as `PDP2ht` does. Run it as
`residual.py --solver tmxl`.

**Novelty check.** y-XL / y-MXL for overdetermined bilinear systems is published
(arXiv 2006.09442, AMC 2021). Block-structured Gröbner bases for this PDP are in
Faugère-Perret-Petit-Renault 2012. We found no use of a one-block closure on the projected m = 2
residual system, so this is at most a new combination of known parts.

**Measurements**, against the full closure. All are non-decomposable targets refuted by both,
geomtraceu seed 1, at n = 41 unless marked. Data: `results/residual-tmxl.jsonl`.

| d | N | degree (t-closure) | columns (t-closure / full) | word operations (t-closure / full) | t-closure (rps) | `2^d` enumeration (rps) |
|---|---|---|---|---|---|---|
| 9 | 26 | 3 | 912 / 2952 | 5.2e5 / 2.7e7 | 1.6e8 | 2.3e9 |
| 12 | 30 | 4 | 6176 / 31931 | 2.1e8 / 4.2e10 | 6.3e10 | 1.8e10 |
| 15 | 34 | 4 | 12885 / 52956 | 1.6e9 / 2.2e11 | 4.7e11 | 1.4e11 |
| 18 | 38 | 4 | 23808 / 82993 | 8.9e9 / 9.3e11 | 2.7e12 | 1.2e12 |
| 21 (n = 47, l = 23) | 44 | **5** (degree 4: rank 28684 of 43473, no linear pivot; degree 5 refutes both eps branches) | 201477 at degree 5 | 7.9e12 per branch (91 min) | — | about 3 s (C enumeration) |
| 24 (n = 53, l = 26) | 50 | **>= 5** (degree 4: rank 42088 of 73401) | 73401 at degree 4 | 1.3e11 | — | — |

The t-only closure needs the same degree as the full closure, at 14-100x less work. The degree
steps from 4 to 5 between `d = 18` and `d = 21`, nine dimensions after the step from 3 to 4. So
the degree grows about linearly, roughly `2 + d/9`.

**Verdict.**

- **Exponent.** With degree about `d/9`, the t-closure has about `l C(d, d/9) ~ 2^(0.5 d)` columns,
  and elimination costs `2^d` (sparse) to `2^(1.5 d)` (dense). That is no exponent below
  enumeration.
- **Measured.** It is cheaper than enumeration only at `d <= 9`, where `PDP2ht` is already cheap,
  and 2-3.5x costlier at `d = 12-18`.
- **Hybrid.** The best use is a hybrid: guess `d - 9` of the t bits and close the remaining 9 at
  degree 3. That keeps the `2^d` slope and changes only the constant: 14x in calibrated rps at
  `d = 9`, and about 1x against a well-optimized enumeration in raw word operations.

It does not meet the goal: it does not stay cheap above the limit.

**The asymptotic exponent of the closure family** (`results/residual-tmxl-deg5.jsonl`). The
degree-5 t-closure at `d = 21` refutes: it ends with 23 linear pivots, at rank 173581 of 201477
columns. Its cost is 7.9e12 word operations, single-threaded, against about `2^21 * 1.5 us = 3 s`
for the C enumeration. So the degree steps are 3 to 4 somewhere in `d = 10..12` and 4 to 5 in
`d = 19..21`. The spacing between steps is therefore between 7 and 11 dimensions, a slope
`s = (D - 1)/d` between about 1/11 and 1/7.

- **Columns.** The t-closure at degree D has about `l C(d, D - 1) ~ 2^(H(s) d)` columns.
  At `d = 21` that is already only 0.1 of `2^d`.
- **Best case for elimination.** Sparse elimination (block Wiedemann, cost about
  `columns^2 * row weight`) gives an exponent `2 H(s) d`. That is below `d` only for
  `s < 0.110`. The measured range, 1/11 to 1/7, straddles this threshold: the exponent is
  between 0.88d and 1.2d. At `s = 1/9`, `2 H(s) = 1.007`.
- **Why even that is optimistic, measured** (`certificate.py`, `results/certificate-n41.jsonl`).
  The closure that refutes is a mutant closure, and Wiedemann cannot run one; it needs a plain
  Macaulay matrix.
  - **Plain degree.** The plain t-Macaulay matrix (equations times t-monomials, one explicit
    identity `sum_m m g_m = 1`) refutes only at a higher degree. At n = 41, every target and both
    branches:

    | d | 3 | 4 | 6 | 9 | 12 | 15 |
    |---|---|---|---|---|---|---|
    | plain t-Macaulay degree | 3 | 4 | 4 | 5 | 5 | 6 |
    | mutant t-closure degree | 3 | 3 | 3 | 3 | 4 | 4 |

    At n = 23 the plain degree at `d = 6` is likewise 4 against 3. No degree-3 identity explains
    the degree-3 mutant refutations (Sec. 5, lead 1).
  - **Exponent.** The plain degree steps every 5-6 dimensions, a slope of about 1/6, so the
    Wiedemann exponent is `2 H(1/6) d = 1.3 d`.
  - **Size.** Already at `d = 12` and `d = 15` the plain matrix has 15087 and 98881 columns,
    against `2^d` = 4096 and 32768 candidates. So even linear-time linear algebra on it would lose
    to the enumeration.
- **No crossover at cryptographic size, even so.** Take the most favourable slope, 1/11. The
  measured excess at `d = 21` is about `2^14` (`columns^2 / 2^d`, before row weight), and it
  closes at about 0.12 per dimension. A crossover would need roughly `d > 130`. At n = 131,
  `d <= 65` for every `l <= (n + 1)/2`.

**Conclusion: the algebraic-closure family has no exponent advantage over `2^d` that is visible
at any size, and no advantage at all at cryptographic n.**

## 4d. Candidate 3: CDCL with XOR reasoning on the residual system (tested; rejected)

**Method.** Encode each residual equation as a native XOR clause, with one AND-gate variable per
`x_i t_k` product, and solve with CryptoMiniSat 5.15 (`pycryptosat`, Gauss-Jordan on). This is
`residual.cms_solve`, run by `cms_scan.py`. A SAT answer is checked by rebuilding X, Y from the
model and testing `P1 + P2 = R` (`verify_model`).

**Novelty check.** SAT / XOR-SAT for the PDP is published: WDSat (Trimoska-Ionica-Dequen 2019,
2020), Galbraith-Gebregiyorgis 2014, and `../pdp-scaling` (CryptoMiniSat). All of these solve the
full descent system, `2l` variables with worst case `2^l` after vertex-cover preprocessing. Running
it on the projected residual (`l + d` variables, worst case `2^d`) is a new combination at most.

**Fair baseline.** `htenum.c` is an optimized C enumeration of the residual space. It uses
Gray-code updates of `u`, `u^2` and `p(u)`, Montgomery batch inversion, pclmul multiplication, and
byte tables for the half-trace and the V-syndrome. It runs at about 1.8 us per candidate (both eps
branches), 15x faster than the Python `PDP2ht` path, and agrees with the half-trace solver on 30/30
targets. Timings: `results/enum-scan.jsonl` (`enum_scan.py`, same target streams as `cms_scan.py`).

**Measurements** (`results/cms-scan.jsonl`). All CMS answers agree with the exact enumeration
wherever both ran (45/45), and every SAT model verifies.

| n | l | d | decomposable targets | CMS median | C enumeration median | CMS / enumeration |
|---|---|---|---|---|---|---|
| 41 | 17 | 9 | 0/8 | 0.04 s | 1.1 ms | 40 |
| 41 | 18 | 12 | 0/8 | 1.9 s | 7.5 ms | 250 |
| 41 | 19 | 15 | 2/8 | 1.4 s | 62 ms | 23 |
| 41 | 20 | 18 | 5/8 | 8.7 s | 0.46 s | 19 |
| 59 | 26 | 18 | 0/6 | 16.6 s | 0.65 s | 25 |
| 59 | 27 | 21 | 0/6 | 165 s | 5.5 s | 30 |
| 59 | 28 | 24 | 0/2 (enumeration only) | not run | 42.5 s | — |

Against the slow Python enumeration CMS seemed to grow more slowly than `2^d`. Against the C
baseline it is a constant 20-35x slower from `d = 15` on. On the unsatisfiable n = 59 cells its time
grows 9.9x per 3 dimensions from `d = 18` to `d = 21`, against 8.4x for the enumeration, so the
ratio grows from 25x to 30x.

**Verdict:** rejected. It shows no sub-`2^d` behaviour against a fair baseline.

## 4d'. Against the repository's F4 above the limit (same factor base, `f4_pair.py`)

**The F4 reference.** `../f4-gpu-20260925` holds the repository's fastest Gröbner decomposition
oracle, measured inside complete, verified DLPs. Its runs `IC1N23Cka1fb2071PDP2f4...` use, on
`y^2 + xy = x^3 + x^2 + 1` over `F_2[z]/(z^23 + z^5 + 1)`, the Frobenius-stable base
`ker g(tau)`, with g irreducible factor 0 of `x^23 - 1`.

**The rebuilt base.** `f4_pair.py` rebuilds that base: 2071 geometric points and 45 effective
columns, as in the manifest. The manifest's B = 2071 also counts the 2-torsion point at `x = 0`,
which `FactorBase` excludes, giving 2070. Its `dim V^(2) = 22`, so `d = 10`, above the limit
`(n + 2)/3 = 8.3`.

**Exactness.** `PDP2ht`, both the Python half-trace solver and the C enumeration, agrees with
the exact pair table on 100 planted and 300 ordinary targets (0 mismatches). Of the ordinary
targets, 0.433 decompose, against F4's recorded 26/63 = 0.41. The whole-C path agrees on all 300 ordinary
targets too.

**Per-attempt cost**, one core, on the same VM class as the F4 records:

| PDP oracle on this base | ms per attempt | vs optimized F4 |
|---|---|---|
| F4, reference kernel (`...h573364f3659b`, 3 runs) | 608-614 | 0.1x |
| F4, `f4_gf2` + F5 (`...h45c66064bdd9`, 3 runs) | 59.3-59.5 | 1x |
| `PDP2ht`, Python (`PS1N23Cka1fb2070PDP2hth064cba3edc38`) | 21.5 | 2.8x faster |
| `PDP2ht`, Python projection + `htenum.c` (`PS1N23Cka1fb2070PDP2hth1432532edf77`) | 0.80 | 75x faster |
| the same, whole attempts in C (`ht_attempt_batch`) | 0.087 | 680x faster |

- **Workload.** `W4dc3a8a66d6c`; both PS1 rows are run R1 on it.
- **What the F4 timing includes.** It covers query generation and relation checks, as the F4
  records note. The F4 solver stops at the first root that lifts, while `PDP2ht` returns every
  decomposition.
- **Pairing limits.** The queries are not the same points: the F4 runs used Rust's StdRng. Both
  are wall times on unisolated hosts, so the comparison is exploratory.

So the residual enumeration (`2^10` candidates here) is also well ahead of the repository's best
Gröbner oracle above the limit. That makes it the right baseline for the candidates in Sec. 4.

## 4e. What the best exact oracle gives online, against rho (n = 41, exploratory, all in C)

**Method.** `online_above.py` measures every cost in C on this host, for geomtraceu seed 1. Data:
`results/online-above-c-n41.jsonl`.

- **IC attempt.** One walk addition plus a whole `PDP2ht` attempt: the projection for both eps,
  then the residual enumeration (`htenum.c`, `ht_attempt_batch`). It is timed over 64-20000
  targets in one call.
- **Attempts.** The number of attempts is `1 / p_dec`, from the psi-class prediction. The
  measured hit rate on the same targets agrees within sampling error.
- **Rho step.** A batched affine r-adding walk (`ec_walk_batch`: 256 walks, one Montgomery
  inversion per round), 58 ns per addition. Plain rho is `sqrt(pi r / 2)` steps, 54 ms expected.
  Bernstein-Lange online is `1.77 r^(1/3)` steps, 0.84 ms, with a table of about `r^(1/3) = 2^13`
  points.

So this is a prediction built from measured stage costs, not an IC1 run. The wall times come from
an unisolated host, so it is exploratory.

| l | vs the limit 14.3 | d | attempts | PDP per attempt | one-target online | vs plain rho | vs Bernstein-Lange |
|---|---|---|---|---|---|---|---|
| 13 | below | 0 | 3.3e4 | 2.8 us | 94 ms | 0.57x (slower) | 112x slower |
| 14 | below | 0 | 8.2e3 | 3.9 us | 33 ms | 1.7x faster | 39x slower |
| 15 | +0.7 | 3 | 2.1e3 | 5.5 us | 11 ms | 4.8x faster | 13x slower |
| 16 | +1.7 | 6 | 508 | 9.9 us | **5.1 ms** | **11x faster** | **6.0x slower** |
| 17 | +2.7 | 9 | 128 | 57 us | 7.4 ms | 7.3x faster | 8.7x slower |
| 18 | +3.7 | 12 | 33 | 0.44 ms | 14 ms | 3.8x faster | 17x slower |
| 19 | +4.7 | 15 | 8.5 | 3.7 ms | 32 ms | 1.7x faster | 38x slower |
| 20 | +5.7 | 18 | 2.5 | 28 ms | 71 ms | 0.76x (slower) | 84x slower |

**Reading the table.**

- **Shape.** The online cost is lowest just past the limit (`l = 16`, `d = 6`). After that it
  roughly doubles per added dimension: each step adds 8x to the residual search and cuts the
  attempts only 4x.
- **Bernstein-Lange is never beaten,** even though IC stores `2^l = 2^16` logs against
  Bernstein-Lange's `2^13` points. With equal storage, Bernstein-Lange would be faster still.
- **Plain rho.** IC beats plain rho by up to 11x near the limit. That margin is bought by the
  precomputed logs, which generic rho can equally buy, and it is gone by `l = 20`.

**What the C changes did.** Folding the field reduction with clmul made the enumeration about
53 ns per candidate, against 1.5 us before. `htenum.c` now also handles `u = 0` (a doubling
`R = 2P`), which it used to skip. Doublings have probability about `2^(l - n)` per random target,
so the earlier scans are unaffected in practice. The new test
`test_c_attempt_and_enumeration_match_exact_table` checks both against the exact pair table.

The CryptoMiniSat ratios in Sec. 4d were measured against the slower enumerator, so they
understate the gap by about 28x.

**Superseded:** the first version of this table (`results/online-above-n41.jsonl`). It priced
rho with the Python implementation (3.5 us per step) against a C oracle, and assumed 2 us for the
projection. That inflated IC's margin over rho by about 4x in most rows, and 88x at `l = 13`.

## 5. Open leads (not yet novelty-checked)

1. ~~Explain the degree-3 refutations~~: there is no degree-3 identity behind them. The plain
   t-Macaulay certificate needs degree 4-5 where the mutant closure refutes at degree 3
   (Sec. 4c), so the mutant closure is exploiting higher-degree cancellations, not a short direct
   mechanism.
2. ~~Measure the degree trend beyond `d = 13`~~: done in Sec. 4b-4c with `smxl.c`. The degree is 3
   for `d <= 9`, 4 for `d = 12-18`, 5 at `d = 21` and >= 5 at `d = 24`. Sec. 4c turns this into an
   exponent bound for the whole closure family.
3. **Other decomposition shapes.** Pairs from two subspaces, cosets, and Frobenius twists were
   checked on paper: each needs more unknowns per pair than one subspace. Candidates that change
   the shape fundamentally (not m = 2 over one subspace) still need a literature check.
4. **Further on-paper checks (2026-10-06), none giving a candidate:**
   - **Möbius images of a subspace**, `x in M(V)`. Translations, scalings and the inversion
     `x -> 1/x` all keep S_3 F_2-linear in `(e1, e2)`, for example
     `S_3(1/f1, 1/f2, S) f1^2 f2^2 = 1 + S^2 e1^2 + S e2 + b e2^2`. The unknowns stay
     `e1 in V`, `e2 in V V`, so the residual dimension is unchanged.
   - **More linear consequences from power sums.** `X^3 + Y^3 = u^3 + u p(u)` lies in `V V^2`
     and gives `n - dim(V V^2)` conditions that are quadratic in t. With `dim(V V) = 2l - 1`, V is
     a geometric progression `xi {1, theta, ..., theta^(l-1)}` (the linear Vosper theorem of
     Bachoc-Serra-Zémor, for `2l - 1 < n - 1`). Then `dim(V V^2) = min(n, 3l - 2)`, so above the
     limit there are none. Any other V enlarges `V V`, and each extra dimension adds one to d. We
     did not check whether the quadratic conditions gained could pay for that.
   - **A coordinate in which translation is F_2-affine.** Suppose f is injective on `<G>` and
     `f(P + R) = A_R(f(P))`, with `A_R` an affine map of `F_2^N`. Then `R -> A_R` is a homomorphism
     `<G> -> AGL(N, 2)`. An element of odd prime order r there needs `r | 2^i - 1` for some
     `i <= N`, so `N >= ord_r(2)`, which is typically of the order of r. So no low-degree coordinate turns
     the m = 2 PDP into pure linear algebra. Among degree-2 functions, x is already optimal: the
     correspondence `(f(P), f(R - P))` has bidegree (2, 2).
   - **T-adic lifting over `F_2[T]`.** For a progression `V = xi {theta^i}_(i<l)`, write
     `X = xi A(theta)` and `Y = xi B(theta)`. Since `deg(A B) <= 2l - 2 < n`, the residual is an
     **exact** polynomial identity: `A (A + D) = P(D)` in `F_2[T]`, with `D = A + B` in the
     d-dimensional family U and P F_2-affine. The coefficient of `T^k` is a convolution, so with
     `D(0) = 1` the coefficients of A are fixed one by one from the low end. That is a power-series
     square root, and pruning by degree would need the low coefficients of `P(D)` to depend on few
     of the t. A valuation-echelon basis of U makes `d_j(t)` triangular. But
     `P(D) = xi^(-2) S (HT(xi^2 D(theta)^2) + kappa)`      multiplies by the target S, so every coefficient `P_k(t)` is a dense form in all of t, and no
     pruning remains. The Dickson/ONB-II basis has the same problem.
   - **Meet-in-the-middle on the pair equation.** Write the condition as
     `X Y + L_S(X) + L_S(Y) = c_S`, with `L_S` F_2-linear. Split `V = V_a + V_b` (each of dimension
     `l/2`, sub-progressions). A functional in `(V_a V_b)^perp` kills the cross terms, leaving
     `k = n - dim(V_a V_b) = n - l + 1` separable bits; the `l - d` linear conditions of U add to
     the key.
     - **Cost.** The lists hold `2^l` half-pairs each, and they collide about `2^(5l - 2n - 3)`
       times. The total, about `2^l`, is above `2^d = 2^(3l - n - 2)` for every `l < (n + 2)/2`, and
       equal only at `l = n/2`.
     - **Splitting each candidate u instead.** Since `V = V_a + V_b`, each u in U fixes the
       sum on each half, and a meet-in-the-middle over `x_a`, `x_b` costs `2^(l/2)` per u. The
       half-trace solves each u in `O(1)`.
     - **Why it cannot do better.** Beating `2^d` needs a split of the d-dimensional space U
       itself. But the root `X(u) = u HT(p(u)/u^2)` divides by u, so no functional of it separates
       over `u = u_a + u_b`. It is a preimage search, where generic collision methods give nothing.
   - **Guided enumeration (measured, `bias.py`, `results/bias-n41.jsonl`).** Is a decomposition more
     likely in some part of the residual space? 300 hits per cell, at n = 41 with `l = 16, 17, 18`
     (`d = 6-7, 9-10, 12`; 143246, 38208 and 10716 targets). Each hit u was written as
     `u0 + sum t_k f_k` in the echelon basis.
     - **Weight.** The mean Hamming weight fraction of t is 0.509, 0.496 and 0.505 (standard error
       about 0.01).
     - **Order.** The mean rank in htenum's Gray-code order is 0.509, 0.493 and 0.521 of `2^d`
       (standard error 0.017), and the decile counts are flat.

     Solutions are uniform in the residual space, so no ordering or early abort beats the expected
     `2^(d-1)` candidates of the plain enumeration.
   - **Polynomial-time partial oracles cost the same per relation.**
     - **Construction.** Restrict one summand to a sub-progression `V' ⊂ V` of dimension `l'`.
       S_3 is linear in `(x1 + x2, x1 x2)`, with unknowns in `V x V' V`, of dimension
       `l + (l + l' - 1)`. So the oracle is linear, and polynomial-time, whenever
       `l' <= n + 2 - 2l`, even well above the limit.
     - **Cost.** It sees only the `2^(l + l')` pairs with a summand in V'. A target decomposes that
       way with probability about `2^(l + l' - n)`, so each relation costs
       `2^(n - l - l') = 2^(l - 2)`. That is exactly the per-relation cost of the full residual
       enumeration, `2^(n - 2l) 2^d`.
     - **Covering V.** Each piece holds `2^(l')` of the `2^l` values of the restricted summand, so
       covering V takes at least `2^(l - l') = 2^d` oracle calls.

     Every route built from linear oracles therefore lands on `2^(l - 2)` per relation above the
     limit, consistent with the uniformity just measured.
   - **Courtois's common-factor cover, measured (`gcdcover.py`, `results/gcdcover.jsonl`,
     `test_gcdcover.py`).** For the prefix base, the pairs with `M | x1` and `M | x2`
     (`deg M = delta`) are exactly the decompositions over the sub-base
     `W_M = M * span{1, ..., z^(l - delta - 1)}` of V. W_M is linearizable when V is not. So
     Courtois's GCD guess is a cover of V by `2^delta` such sub-bases. It is the both-summands
     version of the partial oracles just above.
     - **Exact.** Every W_M decomposition is a V decomposition (checked as a subset of the exact
       pair table).
     - **Yield.** The cover keeps 0.58, 0.23 and 0.12 of V's yield at n = 19, l = 8, for
       `delta = 1, 2, 3`, close to `2^-delta`.
     - **Against enumeration on the same V.** One-target online cost uses `2^delta` half-trace calls
       per attempt and the walk step. The cover beats the residual enumeration on the same oversized
       V, down to 0.43x at n = 19, l = 10, delta = 3, where `e(V) = -10`.
     - **Against enumeration at the best l.** It never beats enumeration at the best l over the same
       range: 4.46x against 3.95x rho at n = 19, and 3.10x against 2.70x at n = 23.

     The yield `2^-delta` and the `2^delta` calls give `2^(n - 2l + 2 delta)` subject to
     `3(l - delta) <= n + 2`, minimized at `2^(n/3)` for every delta. That matches the partial-oracle
     bound.

## 5b. Scope: k >= 3 summands

The goal's other case is a k-point method past `sum_(i<=k) dim V^(i) <= n`.

- **No exact linear oracle for k >= 3.** For k >= 3, `S_(k+1)` has degree `2^(k-1)` in each
  variable and is not F_2-linear in the elementary symmetric functions. So no exact
  linear k-point oracle exists. `../linearized-half-decomposition` prices a hypothetical one, and its
  `k = 3, 4` rows assume it as a lower bound.
- **Total cost, even granting that oracle.** That budget already puts the total cost at no less than
  `2^(2n/3)`.
- **Measured k >= 3 methods.** Beyond that, the k >= 3 decomposition methods measured in this
  repository have the known exponents: `m` (WDSat, FES), `m - 1` (hybrid guessing) and `ceil(m/2)`
  (meet in the middle) in the factor-base dimension.
  - CryptoMiniSat and F4 on the descended `S_(m+1)` grow by about `2^4` (m = 3) and `2^7` (m = 4)
    per added dimension (`../pdp-scaling`, finding 1-2).
  - The m = 3 and m = 4 constructions built from the two-point oracle (Courtois Sec. 3; the
    four-point sampler of `../linearized-half-decomposition`) inherit the two-point residual and its
    `2^d`.

So we found no k-point candidate above its limit that was not already measured. The m = 2 residual
studied above is the bottleneck those constructions share.

## 6. Identifiers (AGENTS.md naming convention)

**What gets a PS1 label.** Every measurement above is a PDP-stage profile: an exact factor base
and a point-decomposition solver, with no relation linear algebra or target descent. So each has
`candidate_id: null` and a label `PS1N<n>C<tag>fb<B>PDP2ht h<12hex>`.

- **Hash input.** The hash covers the factor-base record (`FactorBase.record()`: basis, enumerated-set
  digest, B, columns) and the point-decomposition record.
- **Solver variants.** The residual solver is part of the point-decomposition record. So the
  Python and C enumerations, MXL, the full and t-only closures, CryptoMiniSat and the plain
  certificate each have their own label on the same base.
- **Workload IDs.** These hash the exact target stream: seed string, law, filter and target count.
  The count is recovered by replaying the stream against the recorded rows.
- **Run IDs** are `<PS1>W<workload>R<k>`.
- **Where to find them.** `stage_ids.py` builds them; `results/stage-ids.json` holds the full
  records and run IDs.
- **Source hashes** are taken at the commit that last modified each results file. Rows appended to
  a file under earlier code are attributed to that snapshot.
- **Large factor bases.** For `l >= 26`, the `2^l` points are not enumerated here, so B and the
  enumerated-set digest are unknown. The record stays recipe-only and the label is null, as for
  recipe-only fb-archive entries. The workload IDs are still exact.

All cells use the geomtraceu factor base with seed 1, on `EC1N<n>Ckb1` curves. Rows that share a
workload ID were measured on the same targets.

| n | l | d | residual solver | PS1 stage-config ID | workload | targets | run | results file |
|---|---|---|---|---|---|---|---|---|
| 23 | 9 | 3, 4 | mxl | `PS1N23Ckb1fb504PDP2hthd18f7629b0fc` | `W705b1070a327` | 20 | R1 | `residual-n23.jsonl` |
| 23 | 10 | 6, 7 | mxl | `PS1N23Ckb1fb1074PDP2hthef5c705eed18` | `W95f7ead1817f` | 20 | R1 | `residual-n23.jsonl` |
| 23 | 11 | 9 | mxl | `PS1N23Ckb1fb2078PDP2hth6ca69790752c` | `W0079d154b9a5` | 20 | R1 | `residual-n23.jsonl` |
| 23 | 12 | 12 | mxl | `PS1N23Ckb1fb4130PDP2hthf333eddc0748` | `Wfb5b2059c91b` | 12 | R1 | `residual-n23.jsonl` |
| 23 | 13 | 13 | mxl | `PS1N23Ckb1fb8182PDP2hthbe7b1d77c21d` | `W714ffffa75e5` | 12 | R1 | `residual-n23.jsonl` |
| 41 | 15 | 3, 4 | plain-t-macaulay | `PS1N41Ckb1fb32692PDP2hth9d14580caa32` | `Wd68960d13097` | 3 | R1 | `certificate-n41.jsonl` |
| 41 | 15 | 3, 4 | mxl | `PS1N41Ckb1fb32692PDP2hth4667a0968cd2` | `W4324f35e3cff` | 20 | R1 | `residual-n41.jsonl` |
| 41 | 16 | 6 | plain-t-macaulay | `PS1N41Ckb1fb65818PDP2hth595840c4084b` | `W00e6c5560569` | 3 | R1 | `certificate-n41.jsonl` |
| 41 | 16 | 6 | mxl | `PS1N41Ckb1fb65818PDP2hth4fff117d10b8` | `Wf80aba75c38f` | 20 | R1 | `residual-n41.jsonl` |
| 41 | 17 | 9 | plain-t-macaulay | `PS1N41Ckb1fb131098PDP2hth9cbd148c34f8` | `Wcfbe8d331d15` | 3 | R1 | `certificate-n41.jsonl` |
| 41 | 17 | 9 | cms | `PS1N41Ckb1fb131098PDP2hthb978c5a6089d` | `W34df95b0f352` | 8 | R1 | `cms-scan.jsonl` |
| 41 | 17 | 9 | ht-c | `PS1N41Ckb1fb131098PDP2hthdbb7b90edab4` | `W34df95b0f352` | 8 | R1 | `enum-scan.jsonl` |
| 41 | 17 | 9 | mxl | `PS1N41Ckb1fb131098PDP2hth94c3195ad62e` | `W9112ff664a1f` | 20 | R1 | `residual-n41.jsonl` |
| 41 | 17 | 9 | tmxl | `PS1N41Ckb1fb131098PDP2htha0ff06c1638c` | `Wc4afa7744e72` | 3 | R1 | `residual-tmxl.jsonl` |
| 41 | 18 | 12 | plain-t-macaulay | `PS1N41Ckb1fb261930PDP2hth454e894c9f32` | `W3d3733bb301b` | 3 | R1 | `certificate-n41.jsonl` |
| 41 | 18 | 12 | cms | `PS1N41Ckb1fb261930PDP2hth6f1efef4e9f3` | `Wb1f5a3fe35c8` | 8 | R1 | `cms-scan.jsonl` |
| 41 | 18 | 12 | ht-c | `PS1N41Ckb1fb261930PDP2hth67fbf747eb24` | `Wb1f5a3fe35c8` | 8 | R1 | `enum-scan.jsonl` |
| 41 | 18 | 12 | smxl | `PS1N41Ckb1fb261930PDP2hth5f6ea9e4e45c` | `W723548f7a4a9` | 3 | R1 | `residual-smxl-n41.jsonl` |
| 41 | 18 | 12 | tmxl | `PS1N41Ckb1fb261930PDP2htheee44d24f593` | `W723548f7a4a9` | 3 | R1 | `residual-tmxl.jsonl` |
| 41 | 19 | 15 | plain-t-macaulay | `PS1N41Ckb1fb524160PDP2hth5ac3eab1f475` | `W37375c8bef23` | 1 | R1 | `certificate-n41.jsonl` |
| 41 | 19 | 15 | cms | `PS1N41Ckb1fb524160PDP2hthe08aa31b8205` | `W0b6c54923a24` | 8 | R1 | `cms-scan.jsonl` |
| 41 | 19 | 15 | ht-c | `PS1N41Ckb1fb524160PDP2hthd3d96555be3c` | `W0b6c54923a24` | 8 | R1 | `enum-scan.jsonl` |
| 41 | 19 | 15 | smxl | `PS1N41Ckb1fb524160PDP2hthe22ae21401eb` | `Wb8c2d9956a58` | 2 | R1 | `residual-smxl-n41.jsonl` |
| 41 | 19 | 15 | tmxl | `PS1N41Ckb1fb524160PDP2hth1513b985e407` | `W5dfabfe177c9` | 3 | R1 | `residual-tmxl.jsonl` |
| 41 | 20 | 18 | cms | `PS1N41Ckb1fb1048072PDP2hthd70d24b24a36` | `W8ab1c66f139d` | 8 | R1 | `cms-scan.jsonl` |
| 41 | 20 | 18 | ht-c | `PS1N41Ckb1fb1048072PDP2hth068d28d8c351` | `W8ab1c66f139d` | 8 | R1 | `enum-scan.jsonl` |
| 41 | 20 | 18 | smxl | `PS1N41Ckb1fb1048072PDP2hthd97762c5468c` | `W14fe9b6e2e33` | 3 | R1 | `residual-smxl-n41.jsonl` |
| 41 | 20 | 18 | tmxl | `PS1N41Ckb1fb1048072PDP2hth55152fd852cf` | `W14fe9b6e2e33` | 3 | R1 | `residual-tmxl.jsonl` |
| 47 | 23 | 21 | cms | `PS1N47Ckb1fb8388932PDP2hth8251ea10efc4` | `W9d285b2ffa37` | 1 | R1 | `cms-scan.jsonl` |
| 47 | 23 | 21 | ht-c | `PS1N47Ckb1fb8388932PDP2hth944e158f5112` | `Wcff31b74ecee` | 8 | R1 | `enum-scan.jsonl` |
| 47 | 23 | 21 | tmxl | `PS1N47Ckb1fb8388932PDP2hthd88b05fd83a5` | `W8be3584bd6f0` | 1 | R1 | `residual-tmxl-deg5.jsonl` |
| 47 | 23 | 21 | tmxl | `PS1N47Ckb1fb8388932PDP2hthd88b05fd83a5` | `W8be3584bd6f0` | 1 | R2 | `residual-tmxl.jsonl` |
| 53 | 26 | 24 | tmxl | null (B not enumerated) | `W8e8dce397653` | 3 | — | `residual-tmxl.jsonl` |
| 59 | 26 | 18 | cms | null (B not enumerated) | `W07021cb6fff8` | 6 | — | `cms-scan.jsonl` |
| 59 | 26 | 18 | ht-c | null (B not enumerated) | `W8631a57c4bda` | 8 | — | `enum-scan.jsonl` |
| 59 | 27 | 21 | cms | null (B not enumerated) | `W8043a91ad6be` | 6 | — | `cms-scan.jsonl` |
| 59 | 27 | 21 | ht-c | null (B not enumerated) | `Wbf3229ebef01` | 8 | — | `enum-scan.jsonl` |
| 59 | 28 | 24 | ht-c | null (B not enumerated) | `W7f2cc97718ba` | 8 | — | `enum-scan.jsonl` |
| 59 | 29 | 27 | ht-c | null (B not enumerated) | `W307bfcd1d999` | 2 | — | `enum-scan.jsonl` |
| 59 | 29 | 27 | tmxl | null (B not enumerated) | `Waa0f21e6d72c` | 2 | — | `residual-tmxl.jsonl` |

**Full one-target IC runs above the limit.** None of the profiles above is an `IC1` result. The
verified one-target IC1 runs are in `../ic-bench` (suite `online-ht`, 3 runs each, every target
verified by scalar replay). Three of them are above the limit for their base:

| IC1 candidate | d | online speedup vs rho, per run (wall, exploratory) |
|---|---|---|
| `IC1N19Ckb1fb562PDP2htRCsampleLAgaussTDpdpISO0h5169eba26a5b` (random, l = 9) | 8 | 0.09, 0.49, 0.34 |
| `IC1N23Ckb1fb2120PDP2htRCsampleLAgaussTDpdpISO0hb13468522dc8` (kertrace, l = 11) | 11 | 0.46, 0.26, 0.09 |
| `IC1N23Ckb1fb2134PDP2htRCsampleLAgaussTDpdpISO0he29be7078ab2` (random, l = 11) | 10 | 0.59, 0.17, 0.20 |

`IC1N23Ckb1fb534PDP2htRCsampleLAgaussTDpdpISO0hee0f97ad04b3` (geometric, l = 9, d = 2) is just
past the limit; its per-run speedups are 1.25, 0.44 and 13.8. **Every run with `d >= 8` is slower
online than plain rho on the same target.** This agrees with Sec. 2 and Sec. 4e.

The n = 41 online table in Sec. 4e is a **prediction**, not a run. It combines whole `PDP2ht`
attempts and the rho step, both measured in C, with the predicted `p_dec`, so it has no run ID.
