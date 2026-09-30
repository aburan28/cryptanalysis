# Linearized-half decomposition: a slower-growing decomposition that still does not beat rho

An experiment, not an attack. `../frobenius-quotient-m4` ended on the
statement that a sub-`2^61` index calculus on ECC2K-130 needs a decomposition
method whose cost grows more slowly than the known exponents (`m`, `m - 1`,
`ceil(m/2)` in the factor-base size; `../pdp-scaling`). This directory tests
the one algebraic shortcut that is exact and cheap to verify, measures that
it does grow more slowly, and computes what it does for ECC2K-130: nothing
below `2^(2n/3)`.

**Prior art.** The two-point splitting below is essentially known: Courtois,
*On Splitting a Point with Summation Polynomials in Binary Elliptic Curves*
(ePrint 2016/003) gives splitting algorithms "with running time of the order
of `2^(n/3)`" for two and three parts, which is the cost this method reaches
at `l = n/3`. Karabina, *Point Decomposition Problem in Binary Elliptic
Curves* (ePrint 2015/319), works on the same problem with auxiliary
variables. Only the abstracts were read here. What is new in this directory
is an exact, oracle-checked implementation, its measured scaling, and the
full index-calculus accounting at `n = 131`, not the idea.

## The method (`lhd.py`)

Curve `y^2 + xy = x^3 + 1` over `F_2^n`, polynomial basis. Factor base
`F_l = {P : x(P) in V}`, `V = span{1, z, ..., z^(l-1)}`.

**Two-point oracle, exact and polynomial time.** With `e1 = x1 + x2` and
`e2 = x1 x2`, the third summation polynomial at a fixed `x_T` is

    S_3(x1, x2, x_T) = e2^2 + x_T e2 + x_T^2 e1^2 + 1,

which is **`F_2`-linear in `(e1, e2)`**, because squaring is linear in
characteristic 2. `x1, x2 in V` puts `e1 in V` (`l` unknowns) and
`e2 in span{1, ..., z^(2l-2)}` (`2l - 1` unknowns), so "is `T` a signed sum of
two base points" is an `n x (3l - 1)` linear system over `F_2`. The affine
solution space is enumerated, and each solution is split by
`X^2 + e1 X + e2` (half-trace), checked for membership in `V`, lifted, and
re-added. It needs `3l - 1 <= n`.

**Four-point decomposition.** Sample `Q = P_a + P_b` from the base and ask
the oracle about `R - Q`. It hits with probability about `2^(2l - n)`, so a
decomposition costs about `2^(n - 2l)` linear solves, against meet-in-the-
middle's `2^(2l)` group operations. For `n/4 < l <= (n + 1)/3` that is an
exponent `(n - 2l)/l < 2` in `|F|`, below every exponent `../pdp-scaling`
lists, and it *falls* as `l` grows.

## Verification

- **Oracle exactness** (`results/oracle_check.txt`): compared with brute
  force over all signed pairs of the base, half planted and half random
  targets, the oracle returned exactly the same unordered pairs on 200 of
  200 targets at `n = 17, l = 6` (99 with pairs) and 100 of 100 at
  `n = 23, l = 8` (54 with pairs): 0 mismatches.
- **Every decomposition re-adds to `R`** (an assertion in `decompose4`).

## Measured scaling (`summarize.py`)

| n | l | targets solved | median samples | log2 median samples | predicted log2 (n - 2l) | MITM log2 (2l) | exponent in \|F\| (log2 samples / l) | median CPU s |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 31 | 10 | 12/12 | 1639 | 10.7 | 11 | 20 | 1.07 | 2.9 |
| 41 | 14 | 12/12 | 11786 | 13.5 | 13 | 28 | 0.97 | 52.4 |

Cells `(31, 8)` and `(41, 13)` were still running when this table was written.

The measured sample counts track the `2^(n - 2l)` prediction. At `n = 31,
l = 10` a four-point decomposition takes a median of about 3 s of Python.
`../pdp-scaling` records 194 s for CryptoMiniSat on the direct `S_5` at
`n = 31, l = 5`, a factor base 32 times smaller.

## What it does for ECC2K-130 (`lhd_budget.py`, `results/lhd_budget.md`)

| k | max l (linearization) | m | l | log2 columns | log2 relation phase | log2 LA | log2 total | vs rho |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | 44 | 3 | 44 | 44 | 91.0 | 89.6 | 91.5 | +30.6 |
| 3 | 22 | 6 | 22 | 22 | 91.0 | 46.6 | 91.0 | +30.2 |
| 4 | 13 | 10 | 13 | 13 | 96.0 | 29.3 | 96.0 | +35.2 |

`k = 2` is the implemented oracle. The `k = 3, 4` rows assume a linearized
`k`-point oracle whose unknowns are only the symmetric functions
`e_1..e_k` (dimensions `i(l - 1) + 1`). That is a lower bound on its size, so
the rows are optimistic.

Why no row gets close to rho:

1. **The factor base must be linearizable, so it is small, so relations
   are dear.** With a `k`-point oracle, one relation costs `2^(n - k l)`
   calls, and `C = 2^l` relations are needed. Linearization needs
   `sum_{i<=k} dim V^i <= n`, and `dim V^i >= i(l - 1) + 1`. That is equality
   for the polynomial-degree `V`, and for prime `n` the linear
   Cauchy–Davenport bound (Hou–Leung–Xiang; Bachoc–Serra–Zémor, recalled)
   says no subspace does better. So `l <= 2n / (k(k + 1))`, and the relation
   phase is at least `2^(n (1 - 2(k - 1)/(k(k + 1))))`, which is at least
   `2^(2n/3)` for every `k`: `2^87.3` at `n = 131`, plus the oracle cost.
2. **No Frobenius quotient.** `V` is not Frobenius stable (no nontrivial
   stable subspace exists at prime `n`). The orbit union
   `S = union_j sigma^j(V)` does not rescue it: the oracle linearizes only
   same-shift pairs, so the 131x larger base buys a 131x hit rate at 131x the
   calls, and the columns stay `2^l`.

So the method answers half of the question `../frobenius-quotient-m4` left
open. A decomposition whose cost grows more slowly than the known exponents
**exists and is measured here** (and is essentially Courtois 2016). It does
not bring ECC2K-130 below `2^61`: it moves the bottleneck from the
decomposition to the relation count, and the linearization constraint caps
the whole pipeline at `2^(2n/3)`, about 30 bits above rho. Getting below
`2^61` needs a decomposition that stays cheap while `l` is well above the
linearization limit (`l` near `n/4` with the orbit quotient, where the
per-attempt budget of `../frobenius-quotient-m4` is `2^31`). That is exactly where linearization
fails and where Gröbner/SAT are measured to be exponential.

## What this does not claim

- No attack, no relation collection, no discrete logarithm, nothing run on
  the ECC2K-130 challenge.
- Novelty of the method is **not** claimed (see prior art above). The two
  papers were located by search, and only their abstracts were read.
- `lhd_budget.py` is a model (the same conventions as `../pdp-scaling`,
  with the oracle charged `2^4` group operations). The `k >= 3` rows are
  hypothetical.
- The measured cells are toy `n` with Python arithmetic; the exponent
  claim is the sample count, which is implementation independent.

## Reproducing

```sh
python3 lhd.py --n 17 --l 6 --targets 0 --oracle-check 200
python3 lhd.py --n 31 --l 10 --targets 12 --out results/lhd_n31_l10.json
python3 summarize.py --md results/summary.md
python3 lhd_budget.py
```
