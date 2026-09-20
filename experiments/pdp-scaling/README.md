# Point decomposition on E(F_2^n): a scaling measurement

An experiment, not a library feature.  It measures how the cost of the
**point decomposition problem** (PDP) behind a summation-polynomial index
calculus on a binary Koblitz curve grows with the size of the factor base,
using off-the-shelf solvers, and extrapolates to the parameters an attack on
ECC2K-130 would need.  Everything here is Python plus external solvers; the
C library is not involved.  `results/*.csv` are the measurements this
document is built from, and `fit.py` regenerates every table below from them.

## The question

An index calculus on `E(F_2^131)` writes random points as sums of `m` points
whose abscissae lie in an `l`-dimensional `F_2`-subspace `V`, collects about
`2^l` such relations and solves a sparse `2^l x 2^l` system.  For ECC2K-130
the relation count and the linear algebra are cheap on paper once `m >= 5`;
the cost model in the discussion that led here (Pollard rho on the
`<-1, tau>` orbits costs `2^60.8` iterations, and the parameters below are
the ones that maximise what one decomposition may cost while the whole
attack still ties rho) gives

| m | l | PDP calls | linear algebra | budget per PDP (rho iterations) |
|--:|--:|--:|--:|--:|
| 3 | any | — | — | none: linear algebra alone exceeds rho |
| 4 | 29 | `2^48.6` | `2^60.0` | `2^12` |
| 5 | 28 | `2^28.0` | `2^58.3` | `2^33` |
| 6 | 24 | `2^24.0` | `2^50.6` | `2^37` |

So the mechanism that would turn "immune" into an `n^(1/3)`-type attack is a
decomposition of one point into 5 or 6 factor-base points at about `2^33`
operations each.  The literature's record for solving such systems is
`m = 3, n = 53, l = 6` in about 30 s and `m = 4` with `l <= 4`
(Huang–Petit–Shinohara–Takagi 2013; Galbraith–Gebregiyorgis 2014), which
says the record is far away but not *how* the cost grows.  This experiment
measures the growth.

## What is measured

**Curve and field.**  `E_b : y^2 + xy = x^3 + b` over `F_2^n` for prime
`n` from 17 to 61, with `b = 1` (the Koblitz curve of ECC2K-130, so the
extrapolation is to the actual target family) and a random `b` as a control.
`F_2^n` is in a polynomial basis modulo the first irreducible trinomial or
pentanomial of degree `n` (`gf2n.py`).

**Factor base.**  `F_V = {P : x(P) in V}`, `V = span{1, z, ..., z^(l-1)}`,
the choice used in the literature, so `#F_V ~ 2^l`.

**Summation polynomials.**  `S_3` for this curve is
`x1^2 x2^2 + x1^2 x3^2 + x2^2 x3^2 + x1 x2 x3 + b`; `S_4`, `S_5`, `S_6` are
computed once as resultants over `F_2[b]` from the Sylvester matrix
(`sumpoly.py`).  They have 5, 24, 729 and 190,252 monomials and degree
`2^(k-2)` in each variable, and `sumpoly.py` checks each one against actual
point additions on random points before it is used.

**Weil descent.**  With `x_i = sum_j v_ij z^j` and `v^2 = v`, every
`x_i^(2^k)` is `F_2`-linear in the `v_ij`, so `S_{m+1}(x_1, ..., x_m, x(R))`
becomes one polynomial in `m*l` Boolean variables with coefficients in
`F_2^n`; its `n` coefficient bits are the `n` Boolean equations
(`descend.py`, a staged tensor contraction of the coefficient tensor of
`S_{m+1}` with the descents of the powers `x^e`).  The Boolean degree is at
most `sum_i wt(e_i)`: 6 for `m = 3`, 12 for `m = 4`, 15–20 for `m = 5`.
Instance sizes, for orientation: `m = 3, l = 8`: 24 variables, 47k
monomials; `m = 4, l = 5`: 20 variables, 402k monomials; `m = 5, l = 4`:
20 variables, about a million monomials.

**Instances.**  Every instance has a planted decomposition: `m` random
points of `F_V` are added to give `R`, and the descended system for `x(R)`
is checked to vanish on the planted assignment before any solver sees it.
Any solution a solver returns is lifted to points and re-added, and the
result is compared with `R` up to signs (which `S_{m+1}` cannot see).  The
solve time excludes building the instance.  `n` is kept at or above `m*l`
except for a few cells, so the systems are determined or overdetermined,
as they would be in an attack.

**Engines** (`solve.py`), each in its own process with a wall-clock limit:

* `sat` — CryptoMiniSat 5.15 (`pycryptosat`), one thread.  Every monomial
  of degree >= 2 is a Tseitin AND variable and each of the `n` equations is
  one native XOR clause; this is the plain ANF-to-CNF+XOR route.
* `msolve` — msolve 0.10.1 (F4-style Gröbner basis, grevlex) over `F_2`
  with the field equations `v^2 + v` added, one thread; the solution is
  read off the reduced basis, brute-forcing the few free variables when the
  `m!` symmetric solutions leave the basis non-linear.  It stands in for
  Magma's F4, which the literature used and which is faster on `F_2`.
* `wdsat` — [WDSat](https://github.com/mtrimoska/WDSat), the SAT solver
  Trimoska, Ionica and Dequen built for exactly these systems
  ([ePrint 2019/313](https://eprint.iacr.org/2019/313)), with their
  symmetry-breaking option, on *their* model (`symmodel.py`): `S_4` is
  rewritten in the elementary symmetric polynomials `e1, e2, e3` of
  `x1, x2, x3` (12 monomials), the `6l - 3` coefficients of the `e_i` are
  extra variables defined by degree-1/2/3 polynomials in the `3l` core
  variables, and the `n` descended equations are written in those
  coefficients.  Sizes match Table 1 of the paper exactly (767 CNF-XOR
  variables at `l = 6`).  The solver branches on the `3l` core variables
  only, so its worst case is `2^(3l)/3!` conflicts by construction.  `m = 3`
  only, as in the paper.  The direct model cannot be given to WDSat: its ANF
  reader returns wrong models for monomials of degree 4 and above (checked
  on random planted systems: correct at degree <= 3, wrong at degree >= 4),
  and the direct `S_4` descent has degree 6.  The build is per size class
  (WDSat allocates statically); `WDSAT_SRC` points at the checkout, so a
  modified WDSat with the same command line can be dropped in.
* `mitm` — the combinatorial reference: no algebra, meet-in-the-middle on
  the factor base itself, `P_1 + ... + P_k = R - P_{k+1} - ... - P_m` with
  `k = ceil(m/2)`, matched on the abscissa.  It costs exactly
  `2^(l ceil(m/2))` group additions and is what any algebraic method must
  beat.  It is written in Python, so its *time* carries a large constant;
  its exponent is what matters and is known.

**Grid.**  `n in {17, 31, 61}`; `m = 3` with `l = 3..7` (`sat`, `msolve`
to 6), `l = 3..10` (`wdsat`, three seeds) and `l = 3..10` (`mitm`); `m = 4`
with `l = 3..5` (`sat`), `3..4` (`msolve`), `3..8` (`mitm`); `m = 5` with
`l = 3..4` (`sat`), `3..6` (`mitm`).  Two seeds per cell unless stated; the
`l` sweep for an `n` stops after the first timeout (1500 s for `sat`, 1800 s
for `msolve` and `wdsat`).  One 4-core x86-64 container, four jobs at a
time, one thread each.

## Results

Median solve time in seconds over the solved instances (solved/attempted in
parentheses).  Where a cell says timeout, no instance finished within the
limit.

<!-- BEGIN MEASURED -->
**mitm, m = 3**

| n \ l | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|
| 17 | 0.0036 (2/2) | 0.0126 (2/2) | 0.0333 (2/2) | 0.112 (2/2) | 0.445 (2/2) | 1.92 (2/2) | 7.12 (2/2) | 30.8 (2/2) |
| 31 | 0.0054 (2/2) | 0.0165 (2/2) | 0.0669 (2/2) | 0.307 (2/2) | 1.53 (2/2) | 6.03 (2/2) | 23.1 (2/2) | 111 (2/2) |
| 61 | 0.054 (2/2) | 0.142 (2/2) | 0.506 (2/2) | 1.9 (2/2) | 8.57 (2/2) | 31.6 (2/2) | 98.3 (2/2) | 683 (2/2) |

**mitm, m = 4**

| n \ l | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| 17 | 0.0076 (2/2) | 0.0213 (2/2) | 0.0536 (2/2) | 0.161 (2/2) | 0.484 (2/2) | 1.9 (2/2) |
| 31 | 0.0057 (2/2) | 0.0191 (2/2) | 0.156 (2/2) | 1.13 (2/2) | 1.97 (2/2) | 12.2 (2/2) |
| 61 | 0.0895 (2/2) | 0.268 (2/2) | 0.557 (2/2) | 2.47 (2/2) | 9.87 (2/2) | 36.5 (2/2) |

**mitm, m = 5**

| n \ l | 3 | 4 | 5 | 6 |
|---|---|---|---|---|
| 17 | 0.019 (2/2) | 0.127 (2/2) | 0.49 (2/2) | 2.77 (2/2) |
| 31 | 0.0324 (2/2) | 0.153 (2/2) | 1.57 (2/2) | 12.7 (2/2) |
| 61 | 0.345 (2/2) | 1.02 (2/2) | 4.49 (2/2) | 30.7 (2/2) |

**msolve, m = 3**

| n \ l | 3 | 4 | 5 | 6 |
|---|---|---|---|---|
| 17 | 0.0308 (2/2) | 0.89 (2/2) | 184 (2/2) | timeout (0/2) |
| 31 | 0.0672 (2/2) | 0.307 (2/2) | 21 (2/2) |  |

**sat, m = 3**

| n \ l | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|
| 17 | 0.0072 (2/2) | 0.0083 (2/2) | 0.811 (2/2) | 9.01 (2/2) | 701 (2/2) |
| 31 | 0.006 (2/2) | 0.0066 (2/2) | 0.267 (2/2) | 34.5 (2/2) | 226 (2/2) |
| 61 | 0.0052 (2/2) | 0.0144 (2/2) | 0.548 (2/2) | 30.1 (2/2) | 1.55e+03 (2/2) |

**sat, m = 4**

| n \ l | 3 | 4 | 5 |
|---|---|---|---|
| 17 | 0.19 (2/2) | 9.14 (2/2) | 1.37e+03 (1/2) |
| 31 | 0.0115 (2/2) | 2.54 (2/2) | 197 (1/2) |
| 61 | 0.0331 (2/2) | 4.53 (2/2) |  |

**sat, m = 5**

| n \ l | 3 | 4 |
|---|---|---|
| 17 | 0.934 (2/2) | 153 (1/1) |

<!-- END MEASURED -->

**Fits.**  For every engine and `m`, least squares of
`log2(seconds) = a + c*l + d*n` over the solved instances.  `c` is the
number that matters: bits of work per extra dimension of the factor base.
The last column is the exponent of the meet-in-the-middle baseline, which
is exact.

<!-- BEGIN FITS -->
| engine | m | rows | a | c (bits per l) | d (bits per n) | MITM c |
|---|--:|--:|--:|--:|--:|--:|
| mitm | 3 | 48 | -16.0 | 1.94 ± 0.02 | 0.089 ± 0.002 | 2 |
| mitm | 4 | 36 | -15.1 | 1.89 ± 0.06 | 0.085 ± 0.005 | 2 |
| mitm | 5 | 24 | -14.5 | 2.49 ± 0.08 | 0.078 ± 0.005 | 3 |
| msolve | 3 | 12 | -19.7 | 5.55 ± 0.43 | -0.109 ± 0.050 | 2 |
| sat | 3 | 30 | -21.9 | 4.05 ± 0.31 | 0.010 ± 0.024 | 2 |
| sat | 4 | 14 | -24.1 | 6.72 ± 0.80 | -0.046 ± 0.032 | 2 |
<!-- END FITS -->

The `mitm` rows are a check on the fitting procedure: the measured exponent
recovers the known `ceil(m/2)` (for `m = 5` the range `l <= 6` is too
short for the `2^(3l)` half to dominate the `2^(2l)` half, hence 2.5).  The
positive `d` for `mitm` is the cost of Python field arithmetic growing with
`n`, not an algorithmic effect.

The random-curve control (`results/sat_m3_random.csv`, `sat`, `m = 3`,
`n in {31, 61}`, `l = 4..6`) lands inside the spread of the Koblitz rows: the
`b = 1` coefficients do not make the descended systems easier or harder for
the solver.

## Extrapolation to ECC2K-130

The fits evaluated at `n = 131` and the `l` of the cost model above, in
`log2` of rho iterations on one core (one iteration is taken as `10^-7` s,
the order of the published CPU implementations of the ECC2K-130 iteration;
a factor of ten either way moves every entry by 3.3 bits).  "gap" is the
excess over the per-PDP budget.  Because the `n`-trend `d` is measured over
`n <= 61` only, each fit is also shown with `n` held at 61.

<!-- BEGIN EXTRAPOLATION -->
| m | l | PDP calls | budget per PDP | MITM (exact) | msolve (fit) | msolve (fit, n = 61) | sat (fit) | sat (fit, n = 61) |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3 | 44 | — | none: LA alone exceeds rho | 2^88 | 2^234 | 2^241 | 2^181 | 2^180 |
| 4 | 29 | 2^48.6 | 2^12.2 | 2^58 (gap +46) | — | — | 2^188 (gap +176) | 2^191 (gap +179) |
| 4 | 33 | 2^36.6 | none: LA alone exceeds rho | 2^66 | — | — | 2^215 | 2^218 |
| 5 | 28 | 2^28.0 | 2^32.8 | 2^84 (gap +51) | — | — | — | — |
| 6 | 24 | 2^24.0 | 2^36.8 | 2^72 (gap +35) | — | — | — | — |

Pollard rho on the `<-1, tau>` orbits: `2^60.81` iterations, about 6,417 core-years at the assumed rate.  The budget for `m = 4, l = 29` is `2^12.2` iterations, about 0.5 ms; for `m = 5, l = 28` it is `2^32.8`, about 12 minutes.
<!-- END EXTRAPOLATION -->

## Reading the numbers

1. **The algebraic solvers scale worse than enumeration.**  Over the range
   that can be measured at all, SAT on the descended `S_{m+1}` costs about
   `2^4` more per extra dimension of the factor base for `m = 3` and about
   `2^7` for `m = 4`; msolve's F4 grows faster still and drops out at
   `l = 6` for `m = 3`.  The meet-in-the-middle baseline grows by
   `2^ceil(m/2)`, i.e. `2^2` for `m = 3, 4`.  In absolute terms, at
   `l = 5` a SAT solve already costs the equivalent of `2^23` (`m = 3`) to
   `2^31` (`m = 4`) rho iterations against `2^10` group additions for
   meet-in-the-middle, and the Python meet-in-the-middle overtakes the C++
   SAT solver in wall-clock time from `l = 5` on.  In this formulation,
   with these engines, algebra never catches up with enumeration; it falls
   further behind with every unit of `l`.

2. **The dedicated solver is a thousand times faster and has the same
   exponent as exhaustive search.**  WDSat on the symmetrised model solves
   `m = 3, l = 7` in under a second where CryptoMiniSat on the direct model
   needs minutes to half an hour, and it reaches `l = 10`.  Its conflict
   count multiplies by 8 per unit of `l` (see the table; the paper's Table 3
   shows the same factor from `l = 6` to `l = 11`), which is `2^(3l)/3!`
   exactly: it enumerates the `3l` core bits with symmetry breaking and good
   propagation, and nothing more.  Its time slope is `c ~ 3.4` bits per unit
   of `l` against `2` for meet-in-the-middle.  Gray-code exhaustive search
   (Bouillaguet et al.'s FES, `libfes`) is the same enumeration of the
   `m*l` Boolean variables at a few bit operations per candidate instead of
   a SAT conflict: a smaller constant by perhaps `2^8`, the same exponent
   `m`, and it needs the quadratic-only kernels to be replaced by the
   degree-`d` variant since these systems have degree 6 and up.  The
   hybrid "guess `m - 1` blocks, solve the last by linear algebra" has
   exponent `m - 1`.  So the known decomposition methods sit at exponents
   `m` (WDSat, FES), `m - 1` (hybrid) and `ceil(m/2)` (meet-in-the-middle),
   and the budget for ECC2K-130 needs about `1.2`.

3. **The best measured decomposition is the one without algebra, and it is
   35–51 bits short.**  At the ECC2K-130 parameters the meet-in-the-middle
   decomposition costs `2^58` (`m = 4`), `2^84` (`m = 5`) or `2^72`
   (`m = 6`) group additions per point against budgets of `2^12`, `2^33`
   and `2^37`.  The fitted algebraic costs are `2^180`-ish for `m = 4`; the
   exact figure depends on how the `n`-trend is extrapolated, and it does
   not matter, because the honest lower bound on the gap is the baseline's
   46 bits, and the algebra sits well above the baseline.

4. **What the first-fall-degree heuristic would have predicted is not
   what is measured.**  The subexponential claims for `E(F_2^n)` rest on
   the Gröbner cost being close to polynomial in the number of variables at
   fixed `m` (Petit–Quisquater 2012; Semaev 2015).  Polynomial in `l` at
   fixed `m` would be a `c` that shrinks as `l` grows.  The measured `c` is
   4 to 7 bits per unit of `l` and does not shrink between `l = 3` and
   `l = 7`; msolve's cost per step *increases* with `l`, which is the
   degree of regularity climbing, the same thing Kosters and Yeo saw up to
   `n = 40`.  Nothing in the accessible range hints at the regime the
   heuristic needs.

5. **What would have to change.**  An `n^(1/3)`-type attack on ECC2K-130
   through index calculus needs a decomposition algorithm about `2^35` to
   `2^50` times faster than meet-in-the-middle at `l ~ 25–30`.  The generic
   algebraic route starts `2^13`–`2^21` *behind* meet-in-the-middle at
   `l = 5` with a steeper slope; the dedicated solver closes most of that
   constant and none of the slope.  That is not something to tune out with
   better coordinates or a better engine (the literature's symmetric and
   binary-Edwards coordinates buy a fixed factor and a lower degree, not a
   smaller exponent, and WDSat's own bound is `2^(ml)/m!`); it needs a
   decomposition method whose exponent in `l` is below `ceil(m/2)`, which is
   to say a way of bucketing partial sums of points that the group law does
   not offer.  That is the same obstruction that stops Wagner's k-tree
   algorithm from applying to elliptic curves, and it is the whole question.

## Caveats

* The extrapolation runs from `l <= 7` to `l = 29` and from `n <= 61` to
  `n = 131`.  A fit over that distance is a statement about the measured
  trend, not a prediction with error bars that mean anything; it is
  reported because the gap it produces (over 100 bits) is so much larger
  than any plausible correction, and because the baseline's gap (46 bits)
  needs no extrapolation.
* This is the plain formulation: `S_{m+1}` in the `x_i` directly, no
  symmetric variables (Faugère–Gaudry–Huot–Renault), no binary Edwards
  invariants, no symmetry-breaking factor bases (Galbraith–Gebregiyorgis).
  Those lower the degree and remove the `m!` redundancy; in the literature
  they moved the record from `m = 3` to `m = 4`, i.e. by constants.
* msolve is slower than Magma's F4 on `F_2`; the literature's `l = 6` in
  30 s at `n = 53` is our `l = 5` in 20 s at `n = 31` and a timeout at
  `l = 6`.  The slope, not the level, is what is compared.
* `wdsat` runs the upstream solver on the paper's model; a tuned fork will
  move its constant, and the slope only if it changes what is branched on.
  The WDSat rows are satisfiable instances, which the paper notes run
  faster and with more variance than unsatisfiable ones.
* SAT times have the usual large variance (a factor of 30 between two seeds
  of the same cell is common); the fit uses all points, not medians.
* `S_6` needs no `m = 5` extrapolation row because the `m = 5` data are
  too few for a fit; they are in the tables to show the `S_6` machinery
  works and to place the baseline.

## Reproduce

```sh
cd experiments/pdp-scaling
pip install pycryptosat                       # CryptoMiniSat
export MSOLVE=/path/to/msolve                 # https://msolve.lip6.fr, built from source
export WDSAT_SRC=/path/to/WDSat               # git clone https://github.com/mtrimoska/WDSat (built per size class automatically)
python3 symmodel.py 61 8                      # the WDSat model of one instance: sizes, and the planted check
python3 sumpoly.py                            # computes and verifies S_3..S_6 (about 4 min for the S_6 check)
python3 descend.py 61 3 8                     # one instance: size and build time
python3 solve.py --engine sat --n 61 --m 3 --l 6 --seed 1 --timeout 600
python3 run.py --engine sat --m 3 --ns 17,31,61 --ls 3,4,5,6,7 --seeds 2 --timeout 1500 --out results/sat_m3.csv
python3 fit.py results/*.csv                  # the tables above
```

`run.py` resumes: rows already in the CSV are skipped.
