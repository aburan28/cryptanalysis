# Coordinate representative for the j=0 rho orbit

## Frozen question

Can the order-six j=0 orbit reduction in the **repeated Pollard-rho walk**
use fewer field operations than the existing six-hash reduction, while still
recovering and independently verifying a single discrete logarithm? The
reference is commit `56662513c37974a02c5782aa636677ef6ca0db85` at
`src/curve.c:glv_class_reduce`. The only proposed algorithm change is the
orbit representative and its exponent correction. The reference and candidate
will follow different walk trajectories, so equal operation counts or equal
intermediate points are not expected.

## Exact rule and proof obligation

For `y^2 = x^3 + b` with `p = 1 (mod 3)`, let
`psi(x,y) = (beta*x,-y)`, where `beta^3 = 1` and `beta != 1`.
Compute `x0=x`, `x1=beta*x`, `x2=beta*x1` in Montgomery form. Choose the
smallest unsigned Montgomery x word, breaking ties by the smallest index
`j` in `{0,1,2}`. Independently choose `ymin=min(y,p-y)` (or `y=0`). Set
`Y=(xj,ymin)`. Let `s=1` when `ymin=p-y` differed from the input. Return
`k=j+3*((j mod 2) XOR s)`. Then `Y=psi^k(P)`, including x=0 and y=0.
For the point at infinity return `k=0` and leave it unchanged. The rho
coefficients must be multiplied by `lambda^k mod n` exactly as before.

The representative is invariant under all six input rotations and the
returned power must reconstruct it from each rotated input. These are
correctness requirements, not performance evidence. Montgomery word order
defines a valid deterministic class representative because Montgomery
encoding is bijective. The candidate uses two field multiplications and
one point hash per ordinary reduction; the reference applies five
endomorphisms and six point hashes. No CPU speedup is inferred from this
operation count.

## Evaluation contract

1. Directly check the orbit rule and scalar coefficient correction on the
   named j=0 curves and boundary points, including the identity, x=0 when
   present, and all six rotations of deterministic subgroup points. Keep the
   generic and j=1728 reducers on their existing path.
2. Run the existing curve and rho correctness suites in release and with
   undefined-behavior sanitization. For every completed DLP, replay
   `x*G=Q` independently.
3. A one-target rho comparison uses one frozen public point for both
   executables, includes target-dependent multiplier-table setup, walk,
   collision recovery, and scalar replay in the online interval, and
   records failures. A many-target mean is only a diagnostic.
4. A CPU wall-time claim requires an accepted receipt from
   `docs/ISOLATED_BENCHMARKS.md`. Until then timings on this host are
   exploratory and the speedup is unknown.

This design is an implementation candidate; it makes no academic novelty
claim and no speedup claim.
