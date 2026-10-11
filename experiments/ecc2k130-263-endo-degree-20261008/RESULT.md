# Degree-263 descendant: the first nonscalar endomorphism has degree 121,046

The verified ECC2K-130 descending route changes the endomorphism order from
the maximal order of discriminant `-7` to the conductor-263 order of
discriminant `-484183`. The latter's smallest endomorphism outside integer
multiplication has degree **121,046**, while the source has the degree-2
Frobenius. Thus direct coordinate squaring cannot supply the native
descendant with the source's cheap orbit action. The mapped source action
remains available on the prime subgroup through the explicit degree-263
route; its inverse-map and scalar-correction costs belong to any measured
transported policy.

The same exact screen shows that a static two-summand base would need at
least **3,689,348,814,741,910,323** usable subgroup points for even 1%
one-query support of a uniformly sampled nonidentity target. Even perfect
sign-and-Frobenius orbit packing would leave at least
**14,081,484,025,732,483** log columns, or
**1,760,185,503,216,561 bytes** at one bit per column. The frozen
equal-size W24 base (`B=16,772,828`) has a two-summand support upper bound
of `140663887945206 / (r-1)`, approximately `2.06687e-25`.

## Endomorphism-order calculation

The [verified route manifest](../koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json)
records source curve `EC1N131Ckb1h136f03e58c98`, descendant
`EC1N131Cbinh833014327b07`, descending degree `263`, source conductor
`1`, and descendant conductor `263`. The source model
`y² + xy = x³ + 1` has four points over `F₂`, so its geometric Frobenius
`π₂` has trace `-1`. Set `τ = -π₂`; then `τ² - τ + 2 = 0`,
`O_K = Z[τ]`, and `disc(O_K) = -7`. The ordinary-order conductor rule gives
`End(E_desc) = Z + 263 Zτ` and discriminant `-7·263² = -484183`.

For any noninteger endomorphism `α = a + 263bτ`, with integers `a` and
`b ≠ 0`, its degree is its quadratic norm:

`4 deg(α) = (2a + 263b)² + 7·263² b²`.

At `|b|=1`, the first square is odd and is at least `1`. Equality gives
`deg(α) = (1 + 7·263²)/4 = 121046`, attained at
`(a,b)=(-132,1),(-131,1),(131,-1),(132,-1)`.
For `|b|≥2`, the second term alone gives `deg(α)≥7·263² = 484183`.
This proves the global minimum. Degree is an algebraic invariant; it is
not an evaluation-time ratio. The stage-cost question for transported
source Frobenius remains an empirical comparison using the already frozen
four-policy workload and charged map calls. The ordinary isogeny/order
relationship follows the framework in
[Kohel's thesis](https://www.i2m.univ-amu.fr/perso/david.kohel/pub/thesis.pdf);
the exact conductors and route are supplied by the local manifest.

## Two-summand support calculation

For a static factor base of `B` distinct points in the prime subgroup,
unordered pairs with repetition number at most `B(B+1)/2`. Multiple pairs
may have the same sum. Under one uniform nonidentity target query in a
subgroup of order
`r = 680564733841876926932320129493409985129`, the hit probability is
therefore at most `B(B+1)/(2(r-1))`. The least integer `B` whose upper
bound reaches `0.01` is `3689348814741910323`: the exact boundary is
`50(B-1)B < r-1 ≤ 50B(B+1)`.

For the source's sign-and-order-131 Frobenius quotient, each nonidentity
orbit has `262` points: 131 is prime, Frobenius-fixed subgroup points would
lie in `E(F₂)` of order four, and the subgroup order is odd and coprime to
four. Since Frobenius has odd order on every nonidentity subgroup point,
its orbit also cannot contain the point's negative. Achieving the
two-summand threshold with an orbit-closed base therefore takes at least
`ceil(B/262)` columns and
`ceil(columns/8)` bytes even at one bit per column. This is a lower bound
on a highly optimistic log-vector representation; it does not price
relations, construction, solver state, or target handling. On the
descendant, such a quotient would require the transported action and its
costs. The exact W24 base size comes from the frozen
[`Q1420` configuration](../ecc2k130-263-equal-w24-workload-20261005/CONFIG.json).

This screen removes static two-summand PDP from the next W24 comparison.
The existing W24/m6 and W28/m5 policies address different arities and
remain governed by held-out ordinary-query success, verified novel rank,
complete one-target recovery, and the paired rho interval. The catalog
keeps these configurations as proposals until their complete candidate
manifests and measurements exist.

## Reproduction

The [integer-only verifier](verify.py) reads the exact route manifest and
the frozen W24 configuration. It checks the latter's route SHA-256, both
curve IDs and subgroup orders, the source `F₂` point count, the norm
minimizers and global bound, the 1% integer boundary, and the W24 support
fraction. Its [receipt](result.json) contains the input hashes and exact
integers. From the repository root:

```sh
python3 experiments/ecc2k130-263-endo-degree-20261008/verify.py --check
```

No timed computation enters this result. The capacity calculation assumes
a static base and a uniform nonidentity target law; guided and adaptive
query laws require their own support analysis.
