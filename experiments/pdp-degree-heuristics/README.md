# Factor-base heuristics for point decomposition: yield and solving degree

An experiment, not a library feature.  It asks, for the summation-polynomial index
calculus on the ECC2K-130 curve family `y^2 + xy = x^3 + 1` over `F_2^n`, how the choice
of factor base changes the two numbers that price relation collection:

* **yield**: the probability that an ordinary subgroup target decomposes over the base;
* **difficulty**: the degree at which a Gröbner-type solver settles one point-decomposition
  query (PDP), and the work that costs.

It measures both exactly on small fields, for seven factor-base families at matched size,
and turns what it finds into heuristics that can be computed from the factor base
alone.  It also provides an online monitor for a relation-collection run.

**Summary of findings** (details and uncertainties below):

1. **For two summands, one structural number sets the solving degree.** Call
   `e = n − dim V − dim V^(2)` the linearization excess, where `V^(2)` is the span of
   products of pairs of elements of `V`.  Over 656 factor bases (7 families, 9 fields),
   the closure (F4/MutantXL-style) solving degree is
   `D = 2 + [e < −3.5] + [e < −8.5]`.  Its mean absolute error is 0.06 degrees, and 0.08
   when each field size is held out in turn.  Plain XL follows a similar rule
   (error 0.15).  Degree 2 means linear algebra on the equations, closed under multiplying
   the fallen linear polynomials by variables.
2. **The factor base controls `e`, and geometric progressions are optimal.** For prime `n`,
   `dim V^(2) ≥ 2l − 1`, and below `n − 1` only the progressions `c·span{1, g, …, g^(l−1)}`
   attain it.  The literature's `span{1, z, …, z^(l−1)}` is one of them.  In the cells where
   the rule puts a random base a degree higher, the progressions are 15–40 times cheaper
   per query and per relation on average, and up to 100 times.  Elsewhere they are
   1.5–2 times cheaper.  The yield is the same.
3. **Yield and degree are separate levers, and they combine.** The mean number of
   decompositions is fixed exactly by `|F|` and the classes of factor-base points in
   `E/⟨G⟩`.  The naive `|F|^m/#E` is off by up to 2.2×, and a Poisson step turns the mean
   into `P(decomposable)` to within 2–3%.  The yield does not follow the product profile.
   A progression placed inside `ker(Tr)` (family `geomtrace`) keeps the minimal profile and
   gets the kernel-of-trace doubling of the yield.
4. **The degree of regularity is the wrong proxy here.** The homogeneous degree of
   regularity of these systems is exactly `l + 1`, because the two-summand top parts are
   bilinear across the variable blocks.  The solving degree is 2–4.  The semi-regular
   prediction misses the solving degree by 0.5–1.2 degrees on average.  The first fall
   degree is the base degree for 95% of queries, whatever the base.
5. **For three summands the formulation decides whether the factor base matters.**
   In the direct formulation (unknowns are the coordinates of the `x_i`) the solving degree
   is set by the system's size.  The family moves it by at most one degree (at `l = 4`,
   from `n = 29` on), and the cost by 1–8×.  In the symmetric formulation (unknowns are the
   coordinates of `e_k ∈ V^(k)`, as in FPPR and WDSat), the number of unknowns *is*
   `Σ_k dim V^(k)`: 15 against 19 at `l = 3`, and 21 against 34 at `l = 4`.  At `l = 3`
   the progressions are 15–40× cheaper per query at equal degree, and 500–1,500× cheaper
   where the random base needs one more degree.
6. **Check the achievable rank before collecting.** On these cofactor-4 curves, a
   two-summand relation matrix has rank `#columns − 1` unless the base contains a
   4-torsion point or lies in `ker(Tr)`.  A collector that waits for full rank never
   stops.  The target logs are still determined; the complete collections (section 7)
   solve modulo the kernel and verify fresh targets by descent.

None of this is an IC result.  Every profile row is a PDP-stage profile
(`candidate_id: null`), the recorded collections are toy DLPs without one calibrated cost
unit (`../ic-bench` reruns them as named, calibrated `IC1` runs), and the fields are far from ECC2K-130.  Section 8 applies the structure-only parts at
`n = 131`, and section 9 lists the limits.

## 1. Quick start

```sh
cd experiments/pdp-degree-heuristics
python3 -m pytest -q                         # 26 tests, ~3 s (numpy; gcc builds pdpkernel.c on first use)

# profile factor bases on one curve and one frozen target workload
python3 profile.py --n 23 --m 2 --l 6,7,8 --families prefix,geomtrace,random --seeds 1 \
    --targets 48 --planted 8 --out /tmp/profile.jsonl
# the symmetric (e_k in V^(k)) formulation of the same question
python3 profile.py --formulation sym --n 31 --m 3 --l 3 --families prefix,random --seeds 1 --targets 16

# a complete relation collection with the online monitor (logs solved mod r and verified)
python3 monitor.py collect --n 19 --m 2 --l 6 --family geomtrace --mode mxl --report-every 2000

# tables, figures and the n = 131 structure-only predictions
python3 heuristics.py results/*.jsonl --n131 --report REPORT.md --update-readme README.md
python3 figures.py results/*.jsonl
```

`sweep.sh`, `sweep_sym.sh`, `sweep_extra.sh` and `collect.sh` regenerate every receipt
under `results/`.  They resume, skipping factor bases already recorded.  `REPORT.md` has
every measured cell; this file shows a selection.

## 2. What is measured

**Curves.**  The Koblitz curve `y^2 + xy = x^3 + 1` over `F_2^n` for prime `n` from 13 to 47
(polynomial basis modulo the first irreducible trinomial or pentanomial, as in
`../pdp-scaling`).  The group order comes from the Frobenius trace.  The DLP subgroup is the
largest prime factor `r` of `#E`, with cofactor `h` (4 for n = 13, 19, 23, 41; larger
otherwise).  Every curve carries its AGENTS.md curve ID, `EC1N<n>Ckb1h<12hex>`.

**Factor bases.**  `F_V = {P : x(P) ∈ V}` for an `l`-dimensional subspace `V`.  The families:

| family | `V` | product profile `dim V^(k)` |
|---|---|---|
| `prefix` | `span{1, z, …, z^(l−1)}` | minimal: `k(l−1)+1` |
| `geometric` | `c·span{1, g, …, g^(l−1)}`, random `c, g` | minimal |
| `geomtrace` | a geometric progression inside `ker(Tr)`: `c` solves `Tr(c·g^j) = 0` | minimal |
| `normal` | `span{β, β^2, …, β^(2^(l−1))}` for a normal element `β` | generic |
| `kertrace` | a random subspace of `ker(Tr)` (every point in `2E`) | generic |
| `random` | a uniform random subspace | generic, `min(n, C(l+k−1, k))` |
| `invariant` | a Frobenius-stable subspace (`n = 31`: dims 5, 6) | — |
| `geomtraceu` | `geomtrace` with `c` uniform on the solution space | minimal |

`geomtrace` draws `c` as an integer (not XOR) sum of solution vectors and rejects any base
outside `ker(Tr)`, so each draw succeeds with probability about `2^-l`.  The recorded
receipts replay that sampler, so it is unchanged.  `geomtraceu` is the corrected sampler for
large `l` (for example N131 in `../fb-archive`); its digests differ.

A point is usable when its `r`-component `π_r(P) = [h·(h⁻¹ mod r)]P` is not the identity.
Its relation-matrix column is the `±`-orbit of `π_r(P)`, and also the `τ`-orbit when `V^2 = V`.
Each receipt records `B` (usable points before folding, the `fb<B>` count), the geometric
point count, the strict-subgroup count and the folded column count separately, plus the
SHA-256 of the enumerated point set.

**Workloads.**  Per curve, a frozen list of ordinary targets `R = [k]G` with `k` uniform on
`[1, r−1]`.  Every factor base of that curve sees the same list, and the workload ID
(first 12 hex digits of SHA-256 over the canonical workload record) is in every row.
Planted targets (sums of `m` usable factor-base points in `⟨G⟩`) are correctness controls
and supply the degree distribution of satisfiable queries.  They are never used as a yield
estimate.

**Two PDP formulations.**  *Direct*: `S_{m+1}(x_1, …, x_m, x(R))` Weil-descended over any
basis of `V`, giving `N = m·l` Boolean unknowns and `n` equations of degree ≤ `m(m−1)`.  For
`V = span{1..z^(l−1)}` this is exactly `../pdp-scaling/descend.py`.  *Symmetric*:
`S_{m+1}` rewritten in `e_k = σ_k(x_1, …, x_m)`, each `e_k` expanded over a basis of `V^(k)`.
That gives `N_e = Σ_k dim V^(k)` unknowns.  A solution counts only if
`T^m + e_1 T^(m−1) + … + e_m` splits over `V`; each `e`-solution costs one splitting check.
For `m = 2` the symmetric system is linear, and for `m = 3` it is quadratic.

**Yield.**  Exact: all sums of `m` factor-base points are enumerated, and those in
`⟨G⟩ − {O}` are counted.  This gives `P(decomposable)` and the mean number of ordered
decompositions over *every* subgroup target, with no sampling.  An independent point-sum
oracle checks every sampled target against the algebraic route (descent, Möbius solution
set, lifting); they agree on every target of every run.

**Degrees.**  With `R_D` the row space of the Macaulay matrix `{x^a f_i : |a| + deg f_i ≤ D}`
over `F_2[x]/(x_i^2 + x_i)`, and columns in grevlex order:

* `FFD`, the first degree with `dim(R_D ∩ P_{<D}) > dim R_{D−1}`, a genuinely new
  lower-degree polynomial;
* `D_solve` (XL), the least `D` at which `R_D` contains a Gröbner basis: the Caminata–Gorla
  solving degree.  It is tested exactly: the ideal is radical with a known number `S` of
  solutions, so the test is whether the monomials divisible by no leading monomial number
  exactly `S`.  `S = 0` is a refutation (`1 ∈ R_D`);
* `D_solve` (MXL), the same test on the closure of `R_D` under multiplication by variables
  within degree `D`.  Polynomials that fall below `D` are multiplied again at the same degree,
  which is what MutantXL and the step degree of an F4 run do;
* `D_reg`, the first degree at which the top-degree parts generate every monomial in
  `F_2[x]/(x_i^2)`, set beside the semi-regular prediction `(1+t)^N / Π(1 + t^{d_i})`.

For refutations and unique solutions, which is almost every collection query, `D_solve` is
exactly where an XL or MXL solver stops.  Its cost is charged in **64-bit word XORs in
elimination plus monomial insertions in row building**, counted by the kernel.  The
brute-force solution count that certifies the GB test is recorded separately, as
instrument time.  CryptoMiniSat on the same systems (the `pdp-scaling` CNF-XOR encoding) is
timed as a second, independent difficulty measure.

## 3. The heuristics, and why they should work

**Product profile.**  The symmetric functions `e_k` of `m` factor-base abscissae lie in
`V^(k)`.  For a prime `n` the field has no intermediate subfields, so Hou, Leung and Xiang's
field analogue of Kneser's theorem gives `dim V^(k) ≥ min(n, k(l−1)+1)`.  Bachoc, Serra and
Zémor's analogue of Vosper's theorem shows that, below `n − 1`, equality at `k = 2` forces `V`
to be a geometric progression.  So "a factor base with the smallest product profile"
means exactly "a shifted geometric progression".  The free parameters `(c, g)` can then be
spent on other properties: the trace, the liftable count, Frobenius alignment.

**Linearization rank, two summands.**  `S_3 = e_2^2 + e_1^2 X^2 + e_2 X + b`.  Its
target-independent pieces span a space of Boolean functions of dimension
`ω = 1 + dim V + dim V^(2)`, and every target's `n` equations lie in that space
(`descent.Pieces.structure`).  When `e = n − (ω − 1) > 0` the equations are linearly
dependent there.  So a non-decomposable target is refuted by plain linear algebra with
probability about `1 − 2^(1−e)`: that is the chance that its equations span the whole
`ω`-dimensional space.  Otherwise the fallen linear equations pin `e_1`, which makes
`e_2 = x_1(x_1 + e_1)` linear in `x_1`.  In the symmetric formulation the same number
appears as the unknown count, `N_e = ω − 1`, with `2^(N_e − n)` splitting checks per query.

**Yield.**  Sums of `m` factor-base points land in `⟨G⟩ ⊕ ⟨ψ(F)⟩` with `ψ(P) = [r]P`.  The
estimate is `E[#ordered decompositions] = T_ψ / r`, where `T_ψ` counts ordered `m`-tuples
whose `ψ` images cancel, less those that sum to `O`.

* For two summands this is an identity: a pair sums into `⟨G⟩` exactly when its images
  cancel.  For more summands it treats the `r`-component of a sum as uniform.
* The class counts can be estimated by sampling points when the sums cannot be
  enumerated.
* For a trace-kernel base every point lies in `2E`, so `T_ψ` doubles.

**Online monitor.**  During collection, `CollectionMonitor` keeps:

* the yield per attempt, with a Wilson interval and a Beta prior at the predicted yield;
* the novel-row fraction;
* the solving-degree mix by outcome, and its drift from the prediction;
* the cost per attempt, per relation and per novel row, with bootstrap intervals;
* the abort degree that minimizes cost per relation;
* the projected attempts to the achievable rank, with a standard deviation.

The projection treats reaching that rank as an unequal-probability coupon collector over
the exact per-column hit rates, `E[T] = ∫ (1 − Π_j(1 − e^(−λ_j t))) dt`.  It falls back to
the observed rank-deficit rate when that is larger.

## 4. Two summands: the product profile sets the degree

<!-- BEGIN SEL_M2 -->
| n | l | unknowns | family | dims V^(k) | ω | excess | P(dec) exact | D_solve mxl | base refuted | ops/attempt | ops/relation |
|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|--:|
| 23 | 6 | 12 | prefix | [6, 11, 16] | 18 | 6 | 3.43e-04 | 2:48 | 1 | 485 | 1.41e+06 |
| 23 | 6 | 12 | geometric ×2 | [6, 11, 16] | 18 | 6 | 2.34e-04 | 2:96 | 1 | 511 | 2.19e+06 |
| 23 | 6 | 12 | geomtrace ×2 | [6, 11, 16] | 18 | 6 | 5.66e-04 | 2:96 | 1 | 537 | 9.68e+05 |
| 23 | 6 | 12 | normal ×2 | [6, 21, 23] | 28 | -4 | 3.18e-04 | 2:96 | 1 | 1.38e+03 | 4.84e+06 |
| 23 | 6 | 12 | kertrace ×2 | [6, 21, 23] | 27.5 | -3.5 | 5.27e-04 | 2:95 3:1 | 0.99 | 1.51e+03 | 2.90e+06 |
| 23 | 6 | 12 | random ×2 | [6, 20, 23] | 27 | -3 | 2.37e-04 | 2:96 | 1 | 1.21e+03 | 5.09e+06 |
| 23 | 7 | 14 | prefix | [7, 13, 19] | 21 | 3 | 1.32e-03 | 2:48 | 1 | 902 | 6.84e+05 |
| 23 | 7 | 14 | geometric ×2 | [7, 13, 19] | 21 | 3 | 1.07e-03 | 2:96 | 0.99 | 1.01e+03 | 9.70e+05 |
| 23 | 7 | 14 | geomtrace ×2 | [7, 13, 19] | 21 | 3 | 2.15e-03 | 2:96 | 1 | 1.03e+03 | 4.81e+05 |
| 23 | 7 | 14 | normal ×2 | [7, 23, 23] | 31 | -7 | 7.75e-04 | 3:96 | 0 | 3.71e+04 | 5.02e+07 |
| 23 | 7 | 14 | kertrace ×2 | [7, 23, 23] | 31 | -7 | 2.27e-03 | 3:96 | 0 | 3.17e+04 | 1.40e+07 |
| 23 | 7 | 14 | random ×2 | [7, 23, 23] | 31 | -7 | 1.06e-03 | 3:96 | 0 | 3.34e+04 | 3.16e+07 |
| 23 | 8 | 16 | prefix | [8, 15, 22] | 24 | 0 | 4.51e-03 | 2:47 3:1 | 0.96 | 3.31e+03 | 7.34e+05 |
| 23 | 8 | 16 | geometric ×2 | [8, 15, 22] | 24 | 0 | 3.51e-03 | 2:95 3:1 | 0.98 | 2.97e+03 | 8.49e+05 |
| 23 | 8 | 16 | geomtrace ×2 | [8, 15, 22] | 24 | 0 | 7.47e-03 | 2:77 3:19 | 0.79 | 1.01e+04 | 1.37e+06 |
| 23 | 8 | 16 | normal ×2 | [8, 23, 23] | 32 | -8 | 3.57e-03 | 3:96 | 0 | 3.27e+05 | 9.31e+07 |
| 23 | 8 | 16 | kertrace ×2 | [8, 23, 23] | 32 | -8 | 7.87e-03 | 3:96 | 0 | 3.18e+05 | 4.07e+07 |
| 23 | 8 | 16 | random ×2 | [8, 23, 23] | 32 | -8 | 3.83e-03 | 3:96 | 0 | 3.08e+05 | 8.05e+07 |
| 41 | 6 | 12 | prefix | [6, 11, 16] | 18 | 24 | 1.18e-09 | 2:48 | 1 | 500 | 4.26e+11 |
| 41 | 6 | 12 | geometric ×2 | [6, 11, 16] | 18 | 24 | 1.05e-09 | 2:96 | 1 | 512 | 5.02e+11 |
| 41 | 6 | 12 | geomtrace ×2 | [6, 11, 16] | 18 | 24 | 1.65e-09 | 2:96 | 1 | 509 | 3.09e+11 |
| 41 | 6 | 12 | normal ×2 | [6, 21, 41] | 28 | 14 | 1.57e-09 | 2:96 | 1 | 844 | 5.43e+11 |
| 41 | 6 | 12 | kertrace ×2 | [6, 21, 41] | 28 | 14 | 2.01e-09 | 2:96 | 1 | 850 | 4.38e+11 |
| 41 | 6 | 12 | random ×2 | [6, 21, 41] | 28 | 14 | 1.03e-09 | 2:96 | 1 | 856 | 8.34e+11 |
| 41 | 7 | 14 | prefix | [7, 13, 19] | 21 | 21 | 3.82e-09 | 2:48 | 1 | 856 | 2.24e+11 |
| 41 | 7 | 14 | geometric ×2 | [7, 13, 19] | 21 | 21 | 3.52e-09 | 2:96 | 1 | 814 | 2.35e+11 |
| 41 | 7 | 14 | geomtrace ×2 | [7, 13, 19] | 21 | 21 | 7.30e-09 | 2:96 | 1 | 813 | 1.13e+11 |
| 41 | 7 | 14 | normal ×2 | [7, 28, 41] | 36 | 6 | 5.06e-09 | 2:96 | 1 | 1.64e+03 | 3.25e+11 |
| 41 | 7 | 14 | kertrace ×2 | [7, 28, 41] | 36 | 6 | 7.53e-09 | 2:96 | 1 | 1.66e+03 | 2.23e+11 |
| 41 | 7 | 14 | random ×2 | [7, 28, 41] | 36 | 6 | 3.83e-09 | 2:96 | 1 | 1.69e+03 | 4.40e+11 |
| 41 | 8 | 16 | prefix | [8, 15, 22] | 24 | 18 | 1.54e-08 | 2:48 | 1 | 1.19e+03 | 7.68e+10 |
| 41 | 8 | 16 | geometric ×2 | [8, 15, 22] | 24 | 18 | 1.51e-08 | 2:96 | 1 | 1.17e+03 | 7.77e+10 |
| 41 | 8 | 16 | geomtrace ×2 | [8, 15, 22] | 24 | 18 | 3.21e-08 | 2:96 | 1 | 1.19e+03 | 3.73e+10 |
| 41 | 8 | 16 | normal ×2 | [8, 36, 41] | 45 | -3 | 1.77e-08 | 2:96 | 1 | 3.34e+03 | 1.92e+11 |
| 41 | 8 | 16 | kertrace ×2 | [8, 36, 41] | 45 | -3 | 2.85e-08 | 2:96 | 1 | 3.54e+03 | 1.24e+11 |
| 41 | 8 | 16 | random ×2 | [8, 36, 41] | 45 | -3 | 1.62e-08 | 2:96 | 1 | 3.34e+03 | 2.12e+11 |
<!-- END SEL_M2 -->

![solving degree against linearization excess](figures/excess_vs_degree_m2.png)

![cost per query and per relation at n = 23](figures/cost_vs_l_n23_m2.png)

Structured (prefix, geometric) against random bases, over every matched cell (same curve,
workload and `l`; ratios are geometric means over cells; censored cells excluded):

<!-- BEGIN PAIRED -->
**mxl**

| m | cells | mean ΔD (random − structured) | ΔD > 0 | ΔD < 0 | ops/attempt ratio | ops/relation ratio | P(dec) ratio |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | 57 | +0.14 | 18 | 1 | 2.53 | 3.52 | 0.95 |
| 3 | 31 | +0.25 | 14 | 3 | 1.46 | 1.01 | 0.985 |

**xl**

| m | cells | mean ΔD (random − structured) | ΔD > 0 | ΔD < 0 | ops/attempt ratio | ops/relation ratio | P(dec) ratio |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | 57 | +0.30 | 34 | 1 | 4.03 | 5.74 | 0.95 |
| 3 | 31 | +0.13 | 16 | 0 | 1.47 | 1.28 | 0.985 |

<!-- END PAIRED -->

The average hides where the difference comes from.  Grouped by how many degrees apart
the fitted excess rule places the two bases:

<!-- BEGIN REGIME -->
**mxl**, two summands

| predicted degree gap | cells | measured mean ΔD | ops/attempt ratio: geo-mean (min–max) | ops/relation ratio: geo-mean (min–max) |
|--:|--:|--:|---|---|
| 0 | 45 | +0.00 | 1.51 (1.01–2.84) | 1.54 (0.202–4.61) |
| 1 | 11 | +0.71 | 19.3 (2.76–100) | 24 (1.59–99.6) |
| 2 | 1 | +0.25 | 7.31 (7.31–7.31) | 7.04 (7.04–7.04) |

**xl**, two summands

| predicted degree gap | cells | measured mean ΔD | ops/attempt ratio: geo-mean (min–max) | ops/relation ratio: geo-mean (min–max) |
|--:|--:|--:|---|---|
| 0 | 40 | +0.04 | 1.8 (0.946–23.6) | 1.99 (0.197–26) |
| 1 | 12 | +0.86 | 22.8 (2.08–90.1) | 17.7 (1.61–86.9) |
| 2 | 5 | +0.96 | 38.9 (12.2–109) | 41.5 (11.7–112) |

<!-- END REGIME -->

`geomtrace` rows appear in `REPORT.md` beside the others.  On the same workloads it has
the kernel-of-trace yield and the geometric-progression degree, except near `e = 0`.
The Frobenius-stable bases on `n = 31` show why AGENTS.md counts usable points and not
dimensions.  The 5-dimensional `σ`-stable subspace `W` lifts every abscissa, and its 62
usable points fold into a single relation-matrix column.  The 6-dimensional `F_2 ⊕ W` has
three points in all.  61 of its 64 abscissae do not lift, and the three that do are 2- and
4-torsion, so `B = 0`.

## 5. Heuristics that held up

Accuracy of the structure-only degree predictors, against the measured mean solving
degree per factor base:

<!-- BEGIN PREDICTORS -->
| formulation | m | mode | factor bases | semi-regular D_reg MAE | fall-adjusted MAE | structure-only expected MAE | within-cell Spearman |
|---|--:|---|--:|--:|--:|--:|--:|
| direct | 2 | mxl | 656 | 0.806 | 0.843 | 0.204 | 0.808 (14 cells) |
| direct | 3 | mxl | 309 | 1.23 | 0.525 | 0.827 | 0.931 (8 cells) |
| sym | 2 | mxl | 520 | 0.191 | 0.191 | 0.191 | — (0 cells) |
| sym | 3 | mxl | 233 | 0.486 | 0.769 | 0.486 | 0.914 (3 cells) |
| direct | 2 | xl | 656 | 0.604 | 0.722 | 0.0929 | 0.895 (16 cells) |
| direct | 3 | xl | 309 | 0.497 | 0.698 | 0.854 | 0.494 (2 cells) |
| sym | 2 | xl | 520 | 0.191 | 0.191 | 0.191 | — (0 cells) |
| sym | 3 | xl | 229 | 0.963 | 1.25 | 0.963 | 0.734 (5 cells) |
<!-- END PREDICTORS -->

A step rule on the linearization excess alone, with thresholds fitted by least squares
and scored with each field size held out in turn:

<!-- BEGIN RULES -->
| formulation | m | mode | factor bases | fitted rule on excess e = n − (ω − 1) | MAE (fit) | MAE (leave one n out) |
|---|--:|---|--:|---|--:|--:|
| direct | 2 | mxl | 656 | D = 2 + [e < -3.5] + [e < -8.5] | 0.059 | 0.0823 |
| direct | 3 | mxl | 309 | D = 4 + [e < 22.5] + [e < 3.5] + [e < -39.5] | 0.157 | 0.222 |
| sym | 2 | mxl | 520 | D = 1 | 0.000 | 4.81e-04 |
| sym | 3 | mxl | 233 | D = 2 + [e < -8.5] + [e < -52.5] | 0.184 | 0.316 |
| direct | 2 | xl | 656 | D = 2 + [e < 0.5] + [e < -6.5] + [e < -8.5] | 0.122 | 0.15 |
| direct | 3 | xl | 309 | D = 5 + [e < 9.5] + [e < -2.5] + [e < -20.5] | 0.294 | 0.361 |
| sym | 2 | xl | 520 | D = 1 | 0.000 | 4.81e-04 |
| sym | 3 | xl | 229 | D = 2 + [e < 0.5] + [e < -32.5] | 0.197 | 0.254 |
<!-- END RULES -->

The predicted probability of refutation at the base degree, from `ω`, against the
measured rate.  The model is plain linear algebra on the equations, which is XL's base
event; the closure refutes more.

<!-- BEGIN BASE -->
| predicted p (from ω) | factor bases | mean predicted | measured mxl | measured xl |
|---|--:|--:|--:|--:|
| [0.00, 0.05) | 128 | 0.008 | 0.133 | 0.003 |
| [0.05, 0.30) | 43 | 0.180 | 0.833 | 0.138 |
| [0.30, 0.70) | 28 | 0.561 | 0.978 | 0.633 |
| [0.70, 0.95) | 55 | 0.859 | 0.997 | 0.902 |
| [0.95, 1.00) | 402 | 0.998 | 1.000 | 0.999 |
<!-- END BASE -->

Exact yield against the prediction, over every factor base:

<!-- BEGIN YIELD -->
| m | factor bases (≥ 30 decomposable targets) | E[#decomp]: exact / ψ-class count | E[#decomp]: exact / naive |F|^m/#E | P(decomposable): exact / Poisson from ψ count |
|--:|--:|---|---|---|
| 2 | 276 | 1.000 (1.00–1.00) | 1.086 (0.91–2.22) | 1.016 (1.00–1.16) |
| 3 | 69 | 1.000 (1.00–1.00) | 1.114 (0.85–2.14) | 1.033 (0.86–1.21) |
<!-- END YIELD -->

Degree of regularity against solving degree (direct formulation; `D_reg` measured on the
first targets of each cell):

<!-- BEGIN DREG -->
| m | l | factor bases | homogeneous D_reg (measured) | D_solve xl | D_solve mxl | semi-regular D_reg |
|--:|--:|--:|--:|--:|--:|--:|
| 2 | 3 | 81 | 4 | 2 | 2 | 2.11 |
| 2 | 4 | 81 | 5 | 2.07 | 2 | 2.33 |
| 2 | 5 | 83 | 6 | 2.18 | 2.07 | 2.89 |
| 2 | 6 | 83 | 7 | 2.39 | 2.18 | 3.11 |
<!-- END DREG -->

CryptoMiniSat on the same systems:

<!-- BEGIN SAT -->
| m | cells | geo-mean CryptoMiniSat CPU ratio random/structured | cells where random is slower |
|--:|--:|--:|--:|
| 2 | 57 | 1.12 | 39 |
| 3 | 27 | 1.1 | 15 |
<!-- END SAT -->

## 6. Three summands, and the symmetric formulation

Direct formulation:

<!-- BEGIN SEL_M3 -->
| n | l | unknowns | family | dims V^(k) | ω | excess | P(dec) exact | D_solve mxl | base refuted | ops/attempt | ops/relation |
|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|--:|
| 31 | 3 | 9 | prefix | [3, 5, 7] | 39 | -7 | 0 | 6:32 | 1 | 2.76e+04 | — |
| 31 | 3 | 9 | geometric ×2 | [3, 5, 7] | 45 | -13 | 6.95e-07 | 6:64 | 1 | 3.66e+04 | 2.62e+10 |
| 31 | 3 | 9 | geomtrace ×2 | [3, 5, 7] | 45 | -13 | 0 | 6:64 | 1 | 3.68e+04 | — |
| 31 | 3 | 9 | normal ×2 | [3, 6, 9] | 57 | -25 | 0 | 6:64 | 1 | 6.40e+04 | — |
| 31 | 3 | 9 | kertrace ×2 | [3, 6, 10] | 62 | -30 | 0 | 6:64 | 1 | 8.45e+04 | — |
| 31 | 3 | 9 | random ×2 | [3, 6, 10] | 62 | -30 | 0 | 6:64 | 1 | 7.05e+04 | — |
| 31 | 4 | 12 | prefix | [4, 7, 10] | 65 | -33 | 0 | 6:32 | 1 | 1.87e+07 | — |
| 31 | 4 | 12 | geometric ×2 | [4, 7, 10] | 76 | -44 | 6.95e-07 | 6:64 | 1 | 2.39e+07 | 1.74e+13 |
| 31 | 4 | 12 | geomtrace ×2 | [4, 7, 10] | 74 | -42 | 0 | 6:64 | 1 | 2.38e+07 | — |
| 31 | 4 | 12 | normal ×2 | [4, 10, 17] | 97 | -65 | 0 | 7:64 | 0 | 1.93e+07 | — |
| 31 | 4 | 12 | kertrace ×2 | [4, 10, 20] | 97 | -65 | 0 | 7:64 | 0 | 1.70e+07 | — |
| 31 | 4 | 12 | random ×2 | [4, 10, 20] | 97 | -65 | 6.95e-07 | 7:64 | 0 | 1.69e+07 | 1.17e+13 |
| 47 | 3 | 9 | prefix | [3, 5, 7] | 39 | 9 | 0 | 6:32 | 1 | 6.63e+03 | — |
| 47 | 3 | 9 | geometric ×2 | [3, 5, 7] | 45 | 3 | 0 | 6:64 | 1 | 1.08e+04 | — |
| 47 | 3 | 9 | geomtrace ×2 | [3, 5, 7] | 45 | 3 | 0 | 6:64 | 1 | 1.22e+04 | — |
| 47 | 3 | 9 | normal ×2 | [3, 6, 9] | 57 | -9 | 0 | 6:64 | 1 | 5.09e+04 | — |
| 47 | 3 | 9 | kertrace ×2 | [3, 6, 10] | 62 | -14 | 0 | 6:64 | 1 | 5.39e+04 | — |
| 47 | 3 | 9 | random ×2 | [3, 6, 10] | 62 | -14 | 0 | 6:64 | 1 | 5.44e+04 | — |
| 47 | 4 | 12 | prefix | [4, 7, 10] | 65 | -17 | 0 | 6:32 | 1 | 7.55e+06 | — |
| 47 | 4 | 12 | geometric ×2 | [4, 7, 10] | 76 | -28 | 0 | 6:64 | 1 | 1.09e+07 | — |
| 47 | 4 | 12 | geomtrace ×2 | [4, 7, 10] | 76 | -28 | 0 | 6:64 | 1 | 1.10e+07 | — |
| 47 | 4 | 12 | normal ×2 | [4, 10, 17] | 118 | -70 | 0 | 7:64 | 0 | 3.40e+07 | — |
| 47 | 4 | 12 | kertrace ×2 | [4, 10, 20] | 129 | -81 | 0 | 7:64 | 0 | 2.76e+07 | — |
| 47 | 4 | 12 | random ×2 | [4, 10, 20] | 129 | -81 | 0 | 7:64 | 0 | 2.75e+07 | — |
<!-- END SEL_M3 -->

![three summands at l = 3, both formulations](figures/three_summands_l3.png)

The formulation that suits a base depends on its profile.  For geometric progressions the
symmetric model is about as cheap as the direct one from `n = 23` on.  For random bases it
is several hundred times more expensive, because their `V^(2)` and `V^(3)` add 4 more
unknowns.

Symmetric formulation (unknowns `e_k ∈ V^(k)`; random bases above 22 unknowns are
skipped, which is itself the effect):

<!-- BEGIN SEL_SYM_M3 -->
| n | l | unknowns | family | dims V^(k) | ω | excess | P(dec) exact | D_solve mxl | base refuted | ops/attempt | splits/query | ops/relation |
|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|--:|--:|
| 23 | 3 | 15 | prefix | [3, 5, 7] | 54 | -30 | 2.10e-05 | 3:32 | 0 | 2.02e+05 | 0 | 9.62e+09 |
| 23 | 3 | 15 | geometric ×2 | [3, 5, 7] | 62 | -38 | 1.15e-05 | 3:64 | 0 | 2.18e+05 | 0 | 2.20e+10 |
| 23 | 3 | 15 | geomtrace ×2 | [3, 5, 7] | 61.5 | -37.5 | 4.29e-05 | 3:64 | 0 | 2.35e+05 | 0.0312 | 5.64e+09 |
| 23 | 3 | 18 | normal ×2 | [3, 6, 9] | 75 | -51 | 5.73e-06 | 4:64 | 0 | 9.24e+07 | 0.0156 | 8.25e+12 |
| 23 | 3 | 19 | kertrace ×2 | [3, 6, 10] | 81 | -57 | 1.91e-05 | 4:64 | 0 | 2.12e+08 | 0.172 | 1.16e+13 |
| 23 | 3 | 19 | random ×2 | [3, 6, 10] | 81 | -57 | 1.34e-05 | 4:64 | 0 | 1.80e+08 | 0.0312 | 1.35e+13 |
| 23 | 4 | 21 | prefix | [4, 7, 10] | 78 | -54 | 1.97e-04 | 4:32 | 0 | 6.78e+08 | 0.25 | 3.45e+12 |
| 23 | 4 | 21 | geometric ×2 | [4, 7, 10] | 80 | -56 | 1.67e-04 | 4:64 | 0 | 6.62e+08 | 0.234 | 4.39e+12 |
| 23 | 4 | 21 | geomtrace ×2 | [4, 7, 10] | 80 | -56 | 6.87e-05 | 4:64 | 0 | 7.91e+08 | 0.375 | 1.17e+13 |
| 31 | 3 | 15 | prefix | [3, 5, 7] | 54 | -22 | 0 | 3:32 | 0 | 9.70e+04 | 0 | — |
| 31 | 3 | 15 | geometric ×2 | [3, 5, 7] | 63 | -31 | 6.95e-07 | 3:64 | 0 | 1.16e+05 | 0 | 8.36e+10 |
| 31 | 3 | 15 | geomtrace ×2 | [3, 5, 7] | 63 | -31 | 0 | 3:64 | 0 | 1.16e+05 | 0 | — |
| 31 | 3 | 18 | normal ×2 | [3, 6, 9] | 80 | -48 | 0 | 3:64 | 0 | 1.05e+06 | 0 | — |
| 31 | 3 | 19 | kertrace ×2 | [3, 6, 10] | 97 | -65 | 0 | 4:64 | 0 | 1.68e+08 | 0 | — |
| 31 | 3 | 19 | random ×2 | [3, 6, 10] | 97 | -65 | 0 | 4:64 | 0 | 1.68e+08 | 0 | — |
| 31 | 4 | 21 | prefix | [4, 7, 10] | 80 | -48 | 0 | 4:32 | 0 | 5.15e+08 | 0.0312 | — |
| 31 | 4 | 21 | geometric ×2 | [4, 7, 10] | 88 | -56 | 6.95e-07 | 4:64 | 0 | 4.90e+08 | 0 | 3.52e+14 |
| 31 | 4 | 21 | geomtrace ×2 | [4, 7, 10] | 88 | -56 | 0 | 4:64 | 0 | 4.90e+08 | 0 | — |
| 47 | 3 | 15 | prefix | [3, 5, 7] | 54 | -6 | 0 | 2:32 | 1 | 5.55e+03 | 0 | — |
| 47 | 3 | 15 | geometric ×2 | [3, 5, 7] | 63 | -15 | 0 | 3:64 | 0 | 1.15e+05 | 0 | — |
| 47 | 3 | 15 | geomtrace ×2 | [3, 5, 7] | 63 | -15 | 0 | 3:64 | 0 | 1.15e+05 | 0 | — |
| 47 | 3 | 18 | normal ×2 | [3, 6, 9] | 80 | -32 | 0 | 3:64 | 0 | 4.86e+05 | 0 | — |
| 47 | 3 | 19 | kertrace ×2 | [3, 6, 10] | 118 | -70 | 0 | 3:64 | 0 | 1.43e+06 | 0 | — |
| 47 | 3 | 19 | random ×2 | [3, 6, 10] | 118 | -70 | 0 | 3:64 | 0 | 1.43e+06 | 0 | — |
| 47 | 4 | 21 | prefix | [4, 7, 10] | 80 | -32 | 0 | 3:32 | 0 | 2.31e+06 | 0 | — |
| 47 | 4 | 21 | geometric ×2 | [4, 7, 10] | 94 | -46 | 0 | 3:64 | 0 | 2.64e+06 | 0 | — |
| 47 | 4 | 21 | geomtrace ×2 | [4, 7, 10] | 94 | -46 | 0 | 3:64 | 0 | 2.64e+06 | 0 | — |
<!-- END SEL_SYM_M3 -->

For two summands the symmetric system is linear (degree 1) for every base, so the whole
difference is in the splitting checks, about `2^(N_e − n)` per query.  At `n = 19, l = 7`
that is about 2 for the progressions and 128 for random bases, at equal yield:

<!-- BEGIN SEL_SYM_M2 -->
| n | l | unknowns | family | dims V^(k) | ω | excess | P(dec) exact | D_solve mxl | base refuted | ops/attempt | splits/query | ops/relation |
|--:|--:|--:|---|---|--:|--:|--:|---|--:|--:|--:|--:|
| 19 | 5 | 14 | prefix | [5, 9, 13] | 15 | 5 | 9.93e-04 | 1:48 | 0.98 | 154 | 0.0208 | 1.55e+05 |
| 19 | 5 | 14 | geometric ×2 | [5, 9, 13] | 15 | 5 | 1.06e-03 | 1:96 | 0.96 | 157 | 0.0417 | 1.54e+05 |
| 19 | 5 | 14 | geomtrace ×2 | [5, 9, 13] | 15 | 5 | 2.19e-03 | 1:96 | 0.97 | 151 | 0.0312 | 6.89e+04 |
| 19 | 5 | 20 | normal ×2 | [5, 15, 19] | 21 | -1 | 1.14e-03 | 1:96 | 0.24 | 265 | 1.81 | 2.33e+05 |
| 19 | 5 | 20 | kertrace ×2 | [5, 15, 19] | 20.5 | -0.5 | 2.65e-03 | 1:96 | 0.17 | 255 | 2.81 | 9.73e+04 |
| 19 | 5 | 20 | random ×2 | [5, 15, 19] | 21 | -1 | 9.55e-04 | 1:96 | 0.17 | 266 | 2.1 | 2.83e+05 |
| 19 | 6 | 17 | prefix | [6, 11, 16] | 18 | 2 | 4.40e-03 | 1:48 | 0.81 | 220 | 0.229 | 5.00e+04 |
| 19 | 6 | 17 | geometric ×2 | [6, 11, 16] | 18 | 2 | 4.55e-03 | 1:96 | 0.79 | 213 | 0.219 | 4.69e+04 |
| 19 | 6 | 17 | geomtrace ×2 | [6, 11, 16] | 18 | 2 | 8.13e-03 | 1:96 | 0.52 | 219 | 0.635 | 2.72e+04 |
| 19 | 6 | 25 | normal ×2 | [6, 19, 19] | 26 | -6 | 4.84e-03 | 1:96 | 0 | 315 | 64 | 6.58e+04 |
| 19 | 6 | 24 | kertrace ×2 | [6, 18, 19] | 25.5 | -5.5 | 9.11e-03 | 1:96 | 0 | 311 | 96 | 3.47e+04 |
| 19 | 6 | 25 | random ×2 | [6, 19, 19] | 26 | -6 | 3.55e-03 | 1:96 | 0 | 317 | 64 | 9.10e+04 |
| 19 | 7 | 20 | prefix | [7, 13, 19] | 21 | -1 | 0.0188 | 1:48 | 0.15 | 270 | 2.17 | 1.44e+04 |
| 19 | 7 | 20 | geometric ×2 | [7, 13, 19] | 21 | -1 | 0.0138 | 1:96 | 0.23 | 264 | 2 | 1.92e+04 |
| 19 | 7 | 20 | geomtrace ×2 | [7, 13, 19] | 21 | -1 | 0.0364 | 1:96 | 0.1 | 265 | 3.88 | 7.31e+03 |
| 19 | 7 | 26 | normal ×2 | [7, 19, 19] | 27 | -7 | 0.0191 | 1:96 | 0 | 325 | 128 | 1.71e+04 |
| 19 | 7 | 26 | kertrace ×2 | [7, 19, 19] | 27 | -7 | 0.03 | 1:96 | 0 | 326 | 256 | 1.10e+04 |
| 19 | 7 | 26 | random ×2 | [7, 19, 19] | 27 | -7 | 0.0191 | 1:96 | 0 | 324 | 128 | 1.70e+04 |
| 23 | 5 | 14 | prefix | [5, 9, 13] | 15 | 9 | 1.15e-04 | 1:48 | 1 | 147 | 0 | 1.28e+06 |
| 23 | 5 | 14 | geometric ×2 | [5, 9, 13] | 15 | 9 | 7.82e-05 | 1:96 | 0.99 | 153 | 0.0104 | 2.14e+06 |
| 23 | 5 | 14 | geomtrace ×2 | [5, 9, 13] | 15 | 9 | 7.16e-05 | 1:96 | 1 | 146 | 0 | 2.04e+06 |
| 23 | 5 | 20 | normal ×2 | [5, 15, 23] | 21 | 3 | 1.08e-04 | 1:96 | 0.88 | 308 | 0.135 | 3.03e+06 |
| 23 | 5 | 20 | kertrace ×2 | [5, 15, 23] | 21 | 3 | 1.01e-04 | 1:96 | 0.76 | 309 | 0.25 | 3.96e+06 |
| 23 | 5 | 20 | random ×2 | [5, 15, 23] | 21 | 3 | 4.58e-05 | 1:96 | 0.85 | 304 | 0.146 | 6.65e+06 |
| 23 | 6 | 17 | prefix | [6, 11, 16] | 18 | 6 | 3.43e-04 | 1:48 | 0.98 | 211 | 0.0208 | 6.17e+05 |
| 23 | 6 | 17 | geometric ×2 | [6, 11, 16] | 18 | 6 | 2.34e-04 | 1:96 | 0.98 | 221 | 0.0208 | 9.44e+05 |
| 23 | 6 | 17 | geomtrace ×2 | [6, 11, 16] | 18 | 6 | 5.66e-04 | 1:96 | 0.96 | 228 | 0.0417 | 4.10e+05 |
| 23 | 6 | 26 | kertrace | [6, 20, 23] | 27 | -3 | 4.47e-04 | 1:48 | 0 | 421 | 16.3 | 9.43e+05 |
| 23 | 6 | 26 | random ×2 | [6, 20, 23] | 27 | -3 | 2.37e-04 | 1:96 | 0.062 | 417 | 8.33 | 1.76e+06 |
| 23 | 7 | 20 | prefix | [7, 13, 19] | 21 | 3 | 1.32e-03 | 1:48 | 0.88 | 281 | 0.125 | 2.14e+05 |
| 23 | 7 | 20 | geometric ×2 | [7, 13, 19] | 21 | 3 | 1.07e-03 | 1:96 | 0.85 | 308 | 0.156 | 2.96e+05 |
| 23 | 7 | 20 | geomtrace ×2 | [7, 13, 19] | 21 | 3 | 2.15e-03 | 1:96 | 0.79 | 301 | 0.219 | 1.40e+05 |
<!-- END SEL_SYM_M2 -->

<!-- BEGIN PAIRED_SYM -->
**mxl**

| m | cells | mean ΔD (random − structured) | ΔD > 0 | ΔD < 0 | ops/attempt ratio | ops/relation ratio | P(dec) ratio | cells where random needs more / fewer splits per query |
|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 2 | 34 | +0.00 | 6 | 0 | 1.47 | 1.5 | 0.893 | 9 / 0 |
| 3 | 18 | +0.24 | 8 | 0 | 11.7 | 6.6 | 1 | 5 / 0 |

**xl**

| m | cells | mean ΔD (random − structured) | ΔD > 0 | ΔD < 0 | ops/attempt ratio | ops/relation ratio | P(dec) ratio | cells where random needs more / fewer splits per query |
|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 2 | 34 | +0.00 | 6 | 0 | 1.47 | 1.5 | 0.893 | 9 / 0 |
| 3 | 17 | +0.43 | 10 | 1 | 17.6 | 13.4 | 1.11 | 4 / 0 |

<!-- END PAIRED_SYM -->

## 7. Relation collection with the monitor

**Not every factor base can reach full rank, and the monitor has to know this before it
starts.**  In the first collection runs, several bases stopped one short of full rank on
all three target streams, after 200,000 queries each: `geometric` and `random` bases at
`n = 19`.  The complete two-summand relation space (every decomposition of every
subgroup target) was then computed exactly (`monitor.achievable_rank`).  For those bases
its rank is `C − 1`.

The reason is the class of each point in `E/⟨G⟩ ≅ Z/4`.  A pair sums into `⟨G⟩` only if
its classes cancel.  So points of class 1 or 3, which share a column with their negatives,
only ever meet each other, and always with opposite signs.  Every such relation reads
`σ_a e_a − σ_b e_b`, and the vector `σ` on those columns is a kernel.

Two bases escape it:

* the `prefix` base, because `1 ∈ V` puts the 4-torsion point `(1, 0)` in `F`, and its
  relations `R = P + T_4` are single-column rows;
* the trace-zero bases (`kertrace`, `geomtrace`), which have no class-1 or class-3 points
  at all.

The deficiency is not fatal: every decomposition of a subgroup point is orthogonal to the
kernel, so target logs are still determined.  The collection now stops at the achievable
rank, solves with the free column set to 0, and verifies by descending three fresh targets
(`Q + [a]G` until it decomposes) and checking `[log]G = Q`.

These are complete collections with the closure solver, paired on curve and cell, over
independent target streams.  The projection columns score the monitor's forecast, made at
half the achievable rank.

<!-- BEGIN COLLECT -->
| n | m | l | family | seed | columns / achievable rank | attempts | yield observed (exact) | ops/novel row | at 50% rank: projected ± sd | actual remaining | descents verified (attempts) |
|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|---|
| 19 | 2 | 5 | geometric | 1 | 14 / 13 | 23003 | 7.83e-04 (7.64e-04) | 5.67e+05 | 2.67e+04 ± 1.33e+04 | 10597 | 3/3 (515, 997, 35) |
| 19 | 2 | 5 | geometric | 2 | 14 / 13 | 48278 | 8.49e-04 (7.64e-04) | 1.19e+06 | 2.20e+04 ± 1.22e+04 | 41383 | 3/3 (180, 2574, 976) |
| 19 | 2 | 5 | geometric | 3 | 14 / 13 | 19752 | 9.11e-04 (7.64e-04) | 4.86e+05 | 2.11e+04 ± 1.24e+04 | 13079 | 3/3 (556, 13, 1444) |
| 19 | 2 | 5 | geomtrace | 1 | 16 / 16 | 5714 | 3.15e-03 (2.23e-03) | 1.19e+05 | 7.98e+03 ± 5.03e+03 | 2702 | 3/3 (356, 86, 277) |
| 19 | 2 | 5 | geomtrace | 2 | 16 / 16 | 14331 | 2.37e-03 (2.23e-03) | 2.98e+05 | 1.21e+04 ± 6.21e+03 | 11525 | 3/3 (105, 146, 267) |
| 19 | 2 | 5 | geomtrace | 3 | 16 / 16 | 26837 | 2.01e-03 (2.23e-03) | 5.60e+05 | 9.66e+03 ± 5.65e+03 | 21384 | 3/3 (537, 849, 786) |
| 19 | 2 | 5 | kertrace | 1 | 15 / 15 | 34009 | 2.03e-03 (2.26e-03) | 1.53e+06 | 1.72e+04 ± 9.62e+03 | 29473 | 3/3 (327, 26, 165) |
| 19 | 2 | 5 | kertrace | 2 | 15 / 15 | 10071 | 2.28e-03 (2.26e-03) | 4.52e+05 | 1.05e+04 ± 7.22e+03 | 6941 | 3/3 (324, 705, 428) |
| 19 | 2 | 5 | kertrace | 3 | 15 / 15 | 6389 | 3.76e-03 (2.26e-03) | 2.86e+05 | 1.30e+04 ± 8.68e+03 | 4261 | 3/3 (1254, 439, 605) |
| 19 | 2 | 5 | prefix | 1 | 13 / 13 | 22750 | 8.35e-04 (9.93e-04) | 5.59e+05 | 1.51e+04 ± 8.68e+03 | 17678 | 3/3 (328, 154, 120) |
| 19 | 2 | 5 | prefix | 2 | 13 / 13 | 26701 | 1.05e-03 (9.93e-04) | 6.60e+05 | 1.78e+04 ± 8.88e+03 | 16656 | 3/3 (1343, 1377, 19) |
| 19 | 2 | 5 | prefix | 3 | 13 / 13 | 25771 | 8.15e-04 (9.93e-04) | 6.35e+05 | 1.33e+04 ± 8.48e+03 | 17524 | 3/3 (349, 77, 357) |
| 19 | 2 | 5 | random | 1 | 17 / 16 | 24031 | 1.62e-03 (1.12e-03) | 9.42e+05 | 1.86e+04 ± 1.00e+04 | 20089 | 3/3 (1538, 398, 2777) |
| 19 | 2 | 5 | random | 2 | 17 / 16 | 18897 | 1.27e-03 (1.12e-03) | 7.40e+05 | 1.82e+04 ± 9.23e+03 | 12357 | 3/3 (953, 529, 1523) |
| 19 | 2 | 5 | random | 3 | 17 / 16 | 34526 | 1.19e-03 (1.12e-03) | 1.35e+06 | 2.21e+04 ± 1.07e+04 | 26645 | 3/3 (949, 711, 218) |
| 19 | 2 | 6 | geometric | 1 | 33 / 32 | 27731 | 3.71e-03 (4.31e-03) | 5.56e+05 | 1.49e+04 ± 6.04e+03 | 21706 | 3/3 (174, 104, 61) |
| 19 | 2 | 6 | geometric | 2 | 33 / 32 | 12694 | 4.25e-03 (4.31e-03) | 2.56e+05 | 1.41e+04 ± 5.72e+03 | 10825 | 3/3 (624, 193, 103) |
| 19 | 2 | 6 | geometric | 3 | 33 / 32 | 16428 | 4.57e-03 (4.31e-03) | 3.29e+05 | 1.39e+04 ± 5.93e+03 | 11576 | 3/3 (162, 105, 195) |
| 19 | 2 | 6 | geomtrace | 1 | 34 / 34 | 8866 | 0.0104 (9.14e-03) | 2.09e+05 | 6.13e+03 ± 2.44e+03 | 7875 | 3/3 (5, 222, 63) |
| 19 | 2 | 6 | geomtrace | 2 | 34 / 34 | 6806 | 9.99e-03 (9.14e-03) | 1.63e+05 | 5.72e+03 ± 2.33e+03 | 4991 | 3/3 (163, 94, 8) |
| 19 | 2 | 6 | geomtrace | 3 | 34 / 34 | 7948 | 8.56e-03 (9.14e-03) | 1.82e+05 | 5.63e+03 ± 2.48e+03 | 6127 | 3/3 (66, 66, 90) |
| 19 | 2 | 6 | prefix | 1 | 31 / 31 | 26774 | 4.07e-03 (4.40e-03) | 5.54e+05 | 1.49e+04 ± 9.16e+03 | 22591 | 3/3 (443, 182, 114) |
| 19 | 2 | 6 | prefix | 2 | 31 / 31 | 14599 | 4.93e-03 (4.40e-03) | 3.02e+05 | 2.10e+04 ± 1.20e+04 | 10803 | 3/3 (257, 167, 122) |
| 19 | 2 | 6 | prefix | 3 | 31 / 31 | 32308 | 3.44e-03 (4.40e-03) | 6.66e+05 | 1.04e+04 ± 4.3e+03 | 28538 | 3/3 (38, 320, 43) |
| 19 | 2 | 6 | random | 1 | 27 / 26 | 17068 | 2.87e-03 (2.87e-03) | 8.43e+06 | 1.40e+04 ± 6.56e+03 | 10822 | 3/3 (666, 4, 120) |
| 19 | 2 | 6 | random | 2 | 27 / 26 | 29840 | 2.21e-03 (2.87e-03) | 1.47e+07 | 1.49e+04 ± 7.2e+03 | 24454 | 3/3 (726, 237, 204) |
| 19 | 2 | 6 | random | 3 | 27 / 26 | 16702 | 2.51e-03 (2.87e-03) | 8.22e+06 | 1.20e+04 ± 5.45e+03 | 10596 | 3/3 (92, 899, 161) |
| 23 | 2 | 6 | geomtrace | 1 | 30 / 30 | 123861 | 4.60e-04 (4.53e-04) | 2.16e+06 | 8.22e+04 ± 3.99e+04 | 81886 | 3/3 (6974, 1600, 270) |
| 23 | 2 | 6 | prefix | 1 | 36 / 36 | 350639 | 3.08e-04 (3.43e-04) | 4.90e+06 | 1.97e+05 ± 8.31e+04 | 286055 | 3/3 (2602, 5647, 2794) |
| 23 | 2 | 6 | random | 1 | 31 / 30 | 263142 | 2.28e-04 (2.34e-04) | 1.06e+07 | 1.97e+05 ± 8.63e+04 | 192774 | 3/3 (3793, 469, 744) |
| 13 | 3 | 3 | prefix | 1 | 4 / 4 | 139 | 0.0288 (0.028) | 1.33e+07 | 122 | 27 | 3/3 (27, 7, 106) |
| 13 | 3 | 3 | prefix | 2 | 4 / 4 | 300 | 0.02 (0.028) | 2.81e+07 | 56.7 | 258 | 3/3 (11, 28, 2) |
| 13 | 3 | 3 | prefix | 3 | 4 / 4 | 243 | 0.0247 (0.028) | 2.32e+07 | 195 | 54 | 3/3 (51, 12, 25) |
| 13 | 3 | 3 | random | 1 | 2 / 2 | 277 | 7.22e-03 (7.99e-03) | 4.50e+07 | 194 | 237 | 3/3 (65, 123, 48) |
| 13 | 3 | 3 | random | 2 | 2 / 2 | 160 | 0.0125 (7.99e-03) | 2.60e+07 | 251 | 34 | 3/3 (5, 7, 32) |
| 13 | 3 | 3 | random | 3 | 2 / 2 | 83 | 0.0241 (7.99e-03) | 1.45e+07 | 107 | 13 | 3/3 (28, 245, 114) |
<!-- END COLLECT -->

How well the monitor's projection at half rank predicted the remaining attempts.  `z` is
the miss in units of the projected standard deviation; the three-summand runs have no
exact column rates and hence no standard deviation.

<!-- BEGIN COLLECT_CAL -->
| runs with a projection sd | mean z | median z | abs(z) < 1 | abs(z) < 2 |
|--:|--:|--:|--:|--:|
| 30 | +0.25 | -0.03 | 20 | 28 |
<!-- END COLLECT_CAL -->

## 8. What this predicts for ECC2K-130 (prediction, not measurement)

Structure-only numbers at `n = 131` (`heuristics.py --n131`).  The product profile is
exact.  The two-summand `ω` uses the identity checked at toy sizes.  The decomposition
counts use `|F| ≈ 2^l` and `#E = 4r`:

<!-- BEGIN N131 -->
| family | l | dims V^(k), k ≤ 5 | minimum possible | Σ_{k≤3} dim V^(k) | m = 2: ω | m = 2: excess | log2 E[decompositions], m = 2 / 3 / 4 / 5 |
|---|--:|---|---|--:|--:|--:|---|
| prefix | 8 | [8, 15, 22, 29, 36] | [8, 15, 22, 29, 36] | 45 | 24 | 108 | -116.0 / -109.6 / -103.6 / -97.9 |
| prefix | 12 | [12, 23, 34, 45, 56] | [12, 23, 34, 45, 56] | 69 | 36 | 96 | -108.0 / -97.6 / -87.6 / -77.9 |
| prefix | 16 | [16, 31, 46, 61, 76] | [16, 31, 46, 61, 76] | 93 | 48 | 84 | -100.0 / -85.6 / -71.6 / -57.9 |
| prefix | 20 | [20, 39, 58, 77, 96] | [20, 39, 58, 77, 96] | 117 | 60 | 72 | -92.0 / -73.6 / -55.6 / -37.9 |
| prefix | 24 | [24, 47, 70, 93, 116] | [24, 47, 70, 93, 116] | 141 | 72 | 60 | -84.0 / -61.6 / -39.6 / -17.9 |
| prefix | 28 | [28, 55, 82, 109, 131] | [28, 55, 82, 109, 131] | 165 | 84 | 48 | -76.0 / -49.6 / -23.6 / 2.1 |
| geometric | 8 | [8, 15, 22, 29, 36] | [8, 15, 22, 29, 36] | 45 | 24 | 108 | -116.0 / -109.6 / -103.6 / -97.9 |
| geometric | 12 | [12, 23, 34, 45, 56] | [12, 23, 34, 45, 56] | 69 | 36 | 96 | -108.0 / -97.6 / -87.6 / -77.9 |
| geometric | 16 | [16, 31, 46, 61, 76] | [16, 31, 46, 61, 76] | 93 | 48 | 84 | -100.0 / -85.6 / -71.6 / -57.9 |
| geometric | 20 | [20, 39, 58, 77, 96] | [20, 39, 58, 77, 96] | 117 | 60 | 72 | -92.0 / -73.6 / -55.6 / -37.9 |
| geometric | 24 | [24, 47, 70, 93, 116] | [24, 47, 70, 93, 116] | 141 | 72 | 60 | -84.0 / -61.6 / -39.6 / -17.9 |
| geometric | 28 | [28, 55, 82, 109, 131] | [28, 55, 82, 109, 131] | 165 | 84 | 48 | -76.0 / -49.6 / -23.6 / 2.1 |
| normal | 8 | [8, 36, 99, 131, 131] | [8, 15, 22, 29, 36] | 143 | 45 | 87 | -116.0 / -109.6 / -103.6 / -97.9 |
| normal | 12 | [12, 78, 131, 131, 131] | [12, 23, 34, 45, 56] | 221 | 91 | 41 | -108.0 / -97.6 / -87.6 / -77.9 |
| normal | 16 | [16, 131, 131, 131, 131] | [16, 31, 46, 61, 76] | 278 | 148 | -16 | -100.0 / -85.6 / -71.6 / -57.9 |
| normal | 20 | [20, 131, 131, 131, 131] | [20, 39, 58, 77, 96] | 282 | 152 | -20 | -92.0 / -73.6 / -55.6 / -37.9 |
| normal | 24 | [24, 131, 131, 131, 131] | [24, 47, 70, 93, 116] | 286 | 156 | -24 | -84.0 / -61.6 / -39.6 / -17.9 |
| normal | 28 | [28, 131, 131, 131, 131] | [28, 55, 82, 109, 131] | 290 | 160 | -28 | -76.0 / -49.6 / -23.6 / 2.1 |
| random | 8 | [8, 36, 120, 131, 131] | [8, 15, 22, 29, 36] | 164 | 45 | 87 | -116.0 / -109.6 / -103.6 / -97.9 |
| random | 12 | [12, 78, 131, 131, 131] | [12, 23, 34, 45, 56] | 221 | 91 | 41 | -108.0 / -97.6 / -87.6 / -77.9 |
| random | 16 | [16, 131, 131, 131, 131] | [16, 31, 46, 61, 76] | 278 | 148 | -16 | -100.0 / -85.6 / -71.6 / -57.9 |
| random | 20 | [20, 131, 131, 131, 131] | [20, 39, 58, 77, 96] | 282 | 152 | -20 | -92.0 / -73.6 / -55.6 / -37.9 |
| random | 24 | [24, 131, 131, 131, 131] | [24, 47, 70, 93, 116] | 286 | 156 | -24 | -84.0 / -61.6 / -39.6 / -17.9 |
| random | 28 | [28, 131, 131, 131, 131] | [28, 55, 82, 109, 131] | 290 | 160 | -28 | -76.0 / -49.6 / -23.6 / 2.1 |
<!-- END N131 -->

Reading the table:

* The progressions keep the minimal profile through `V^(4)` for `l ≤ 28`, while random and
  normal-basis bases saturate `V^(2)` from `l = 16`.
* For two summands the progressions keep `e ≥ 48` up to `l = 28`.  By the fitted rule,
  that means every query refutes at the base degree.  Random bases fall to `e ≤ −16`,
  outside the rule's measured range (`e ≥ −9`), so their degree there is not predicted.
* For three summands at `l = 28` the symmetric system has 165 unknowns for a progression
  and 290 for a random base, both above the 131 equations.  That leaves about `2^34` or
  `2^159` `e`-solutions to split per query.
* The last column is why none of this reaches ECC2K-130 by itself.  A decomposition is
  expected per target only for five summands at `l = 28` (`2^2.1`), where the direct
  system has 140 unknowns of degree 20 and no degree here is measured.

**How to use this when choosing a factor base and running collection.**

1. *Before choosing a base*, compute the product profile `dim V^(k)` for `k ≤ m`
   (`factor_base.product_profile`).  It is a few thousand field multiplications even at
   `n = 131`.  For two summands, `e = n − l − dim V^(2)` gives the solving degree through
   the fitted rule, and `ω` gives the probability that plain linear algebra refutes a
   query.  Both hold across every family measured here.
2. *Use a geometric progression*: for prime `n` it is the only way to minimize the
   profile.  Spend its free parameter `c` on yield.  With subgroup targets in `2E`, the
   trace-zero choice (`geomtrace`) doubles the yield for the same degree.  At `e ≈ 0` it
   behaves as if the excess were one lower.  Its points satisfy `Σ Tr(x_i) = Tr(x_R)`
   trivially, so the system loses that implied linear relation.
3. *Choose `l` just below a degree threshold.*  The yield grows about fourfold per unit of
   `l` (two summands).  The query cost grows slowly until `e` crosses a threshold, then
   jumps 10–100×.  The cheapest cost per relation is therefore at the largest `l` that
   keeps `e` above the next threshold: `l = 7`–`8` at `n = 23` for geometric progressions,
   against `l = 5`–`6` for random bases.
4. *Before collecting*, compute `monitor.achievable_rank` (or read the `ψ`-class counts)
   and make it the stopping rank.
5. *During collection*, feed `CollectionMonitor` one record per query.
   * Compare the observed yield with the prediction: the Wilson interval should cover it.
   * Compare the observed degree with the rule; drift means the base is not behaving like
     its profile.
   * Abort queries at the degree its table recommends.
   * Read the time to the achievable rank from the coupon-collector projection over the
     exact column rates, with its standard deviation.
6. *Do not steer by the degree of regularity or the first fall degree.*  The homogeneous
   `D_reg` is `l + 1` here, set by the block structure.  The first fall degree is the base
   degree in 95% of two-summand queries, whatever the base.  The semi-regular prediction
   is off by 0.6–0.8 degrees on average.
7. *Match the heuristic to the solver.*  The profile helps linear-algebra solvers.
   CryptoMiniSat on the direct CNF-XOR model gains only about 10% from it.  For three
   summands the direct model hides most of the effect, so profile the symmetric model
   too.

## 9. Conventions and what is not claimed

* Rows are **PDP-stage profiles**: `candidate_id: null`, labelled
  `PS1N<n>Ckb1fb<B>PDP<m>xl[sym]h<12hex>` over the factor-base and point-decomposition
  records (AGENTS.md).  Run IDs are `<PS1-id>W<workload>R<run>`.  In the profiles,
  relation linear algebra and target descent are `none`, so no end-to-end cost or speedup
  is claimed.  The collection runs go further.  They solve the relation matrix modulo its
  kernel and verify three fresh targets by descent (`[log]G = Q`), so each is a complete
  toy DLP.  The recorded collections are still not `IC1` results: their phases are charged
  in wall time and in separate operation units, not one calibrated unit.
* `monitor.collect` now meters every exclusive phase with `opcount.py`'s deterministic
  counters (field, curve, Macaulay, enumeration and mod-`r` classes).  Enumerations that
  the scan's completion test reads are charged to PDP or descent; diagnostics go to
  `instrument`.  `../ic-bench` prices these counters in one calibrated unit, writes
  candidate manifests and emits `IC1` runs.  The recorded receipts above keep their old
  names.
* `ops/relation` in the profile tables is **derived**: mean ordinary-query cost divided by
  the exact decomposition probability.  The collection table measures it.
* Each receipt keeps exclusive phase wall times (setup, factor base, precompute, queries,
  PDP per mode, relation check), the instrument costs, the SHA-256 of every source file
  and the kernel flags.
* The receipts were written over several commits of this directory as features were
  added.  `replay.py` recomputes a sample with the final code and compares every
  deterministic field: operation counts, degree histograms, exact yields, digests and
  workload IDs.  40 of 40 sampled receipts reproduced exactly.
* Correctness controls over all 1,718 profile receipts:
  * all 73,528 ordinary targets agree between the point-sum oracle and the algebraic
    route;
  * the closure solver resolves all 6,112 planted targets, and XL resolves 6,100;
  * no refutation ever met a satisfiable system (the kernel asserts it);
  * the 36 collections verified 108 of 108 descended logs.
* Censored queries are kept, not dropped.  The 12 planted and 128 ordinary queries XL
  left unresolved hit its matrix budget, all in the symmetric three-summand cells at
  `n = 13`.
* The toy fields reach `n = 47` and `N ≤ 18` unknowns.  The step rule is an empirical fit
  in that range.  The `n = 131` table applies structure, not measured degrees, and says
  nothing about `m ≥ 3` degrees at scale.  Two summands cannot beat rho for any factor
  base, because the yield `≈ 2^(2l−n−1)` forces `2^(n+1−l)` queries.

## Next steps

* Done in `../ic-bench`: toy `geomtrace`, `prefix` and `random` bases are `IC1`
  candidates with calibrated totals, paired on frozen workloads.  Next, widen the paired
  workloads at `n = 19, 23` (the `full` suite) and add `m = 3` cells beyond `n = 13`.
* Test whether the excess rule survives beyond `N = 18` with an external F4 (msolve,
  already wired in `../pdp-scaling`).  The rule is a fit, and the thresholds may drift with
  `N`.
* The catalog's `n131_poly_*` profiles are `span{1..z^(l−1)}`, a geometric progression,
  so this work supports that choice.  Its trace-zero sibling is the variant to add.  The
  `n131_onb_hw*` bases are not subspaces, so the product-profile argument says nothing
  about them.
* For `m ≥ 3`, fit a rule on the symmetric model's own size and excess.  The direct
  model's excess does not predict its degree across fields (see the three-summand rules).

## Reproduce

```sh
./sweep.sh && ./sweep_sym.sh && ./collect.sh && ./sweep_extra.sh   # every receipt in results/
python3 heuristics.py results/*.jsonl --n131 --report REPORT.md --update-readme README.md
python3 figures.py results/*.jsonl
```
