# Complete one-hop enumeration through degree 199

Every rational prime degree at most 199 classified as ramified or split by the
P-256 Frobenius discriminant was explicitly enumerated. The completed one-hop
registry contains P-256 plus 48 neighbors. Its union with the depth-three
registry contains 98 unique curves, 28 more than the earlier degree-47 result.

Every retained curve has an explicit rational map from P-256, the same prime
group order, a verified transported generator, and geometric automorphism order
two. No exceptional `j`-invariant or low-norm endomorphism was found.

## Lower-memory recovery and prior failures

Sage's standard `isogenies_prime_degree()` route constructs and fully factors
the degree-ell division polynomial. The original independent panels completed
degrees 59, 97, 101, and 103, but exhausted 8 GiB of PARI stack at degrees 137,
149, and 151. Larger degrees had individual 4 GiB failures.

The replacement method instantiates the classical modular polynomial
`Phi_ell(j1,Y)` directly modulo p. For each simple rational root `j2`, symmetry
provides both first partial derivatives. The modular-multipoints tangent formula
determines the exact normalized codomain, and Sage's BMSS algorithm recovers the
kernel polynomial and explicit map without factoring the full division
polynomial.

As a frozen regression check, this method reproduced both degree-103 candidate
IDs, codomain coefficients, mapped generators, kernel polynomials, and rational
maps exactly. It then completed all ten formerly unresolved degrees: 137, 149,
151, 157, 163, 179, 181, 191, 197, and 199, retaining two neighbors at each.
The ten new degrees consumed 555.64 seconds of wall time. The full process peak
RSS was 299,908 KiB (292.88 MiB), versus the earlier 8 GiB stack failures.

The failed division-polynomial panels remain frozen as superseded evidence.
They consumed 4,165.75 measured wall-seconds, excluding two preliminary failed
monolithic attempts whose raw logs and timings were not retained. This makes
the discovery cost and the algorithmic improvement auditable rather than
silently replacing the failed runs.

## Matched native rho screens

The eight degree-59 through degree-103 additions first received nine
0.5-second trials apiece in one complete timing-position rotation. No paired
95% interval excluded `1.0`.

The 20 degree-137 through degree-199 endpoints were then divided into four
root-controlled blocks of at most six candidates. Each block used 0.5-second
trials and one complete rotation through every timing position. Every curve
used identical fixed-limb Montgomery arithmetic, complete general-`a`
projective formulas, 64-way batch normalization, a 16-entry r-adding table,
and native coefficient tracking. Every post-trial rho relation verified.

No high-degree endpoint triggered the unadjusted screening rule. The largest
point estimate was one degree-199 neighbor at 1.0311x, with paired 95% interval
0.9721–1.0937x. The narrower degree-199 result was 1.0182x with interval
0.9987–1.0382x. Because all 20 intervals include `1.0`, no fresh holdout was
warranted.

Together with the earlier screens, all 97 explicitly retained non-root curves
now have a matched native measurement and none has a reproducible advantage.

## Cost and claim boundary

Discovery and reusable precomputation costs are reported above and in the raw
panel records. Per-key evaluation of the new degree-59 through degree-199 maps
was not timed, so no new amortized end-to-end attack cost is claimed. The
wall-time screens remain exploratory because CPU isolation and frequency
stability were not independently verified. They measure generic rho iteration
cost, not a full P-256 collision experiment.

This is complete for every rational ramified or split prime degree through 199.
It is not an enumeration of larger prime degrees or the entire P-256 isogeny
class, and a finite null screen does not prove that no exceptional curve exists
elsewhere in that class.
