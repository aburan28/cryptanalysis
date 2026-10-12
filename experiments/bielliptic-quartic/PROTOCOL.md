# Bounded bielliptic quartic index calculus

## Scope and hypothesis

Implement the non-hyperelliptic genus-three cover `C: v^4=x^3+a*x+b`
of `E: y^2=x^3+a*x+b` with `pi(x,v)=(x,v^2)`. For the checked
small prime-field fixtures, exact line-section certificates and the
elliptic norm projection should produce enough independent relations to
recover factor-base logarithms and a previously supplied toy target.

This is a correctness diagnostic, not an optimization or a security claim.
The native implementation enforces `5 <= p <= 257` and a prime modulus.
Collection supports nonsingular curves; recovery additionally requires a
prime-order elliptic group and a nonidentity generator. Characteristic
two, extension fields, production-size fields, arbitrary plane quartics,
and general divisor reduction in the full Jacobian are unsupported.

## Frozen inputs and references

The primary fixture has `p=53`, `a=2`, `b=1`, group order `r=59` and
generator `(0,1)`. Its known-answer scalar is a test assertion only and
is never passed to the recovery function. Each correctness target is a
separate supplied point. The regression suite includes the line `v=x-1`,
whose four finite intersections have x coordinates `0,29,36,46`.
Additional input validation, repeated intersections, unsplit residuals,
insufficient rank, certificate tampering, and budget exhaustion must
remain explicit outcomes.

Mathematical references:

- Diem and Thome, *Index calculus in class groups of non-hyperelliptic
  curves of genus three*, sections 2--3:
  https://members.loria.fr/EThome/files/non-he-genus3.pdf
- Diem, *On the discrete logarithm problem for plane curves*:
  https://jtnb.centre-mersenne.org/articles/10.5802/jtnb.815/

## Algorithm and verification boundary

Enumerate the bounded curve's rational points deterministically. Draw
secants through distinct points and remove the known intersection roots;
solve only the residual polynomial of degree at most two. Retain
multiplicities and the point at infinity. Independently reconstruct the
entire line-section polynomial from each certificate, check every point
and incidence, and verify that the projected elliptic sum is the identity.

Only after that check, project to the elliptic factor and fold elliptic
negation. Deck-conjugate points have the same norm image; this does not
make their divisor classes equal in the full Jacobian. Row reduction is
modulo the prime elliptic group order, never the field characteristic.
The generator anchor uses known multiples of the supplied generator, not
an oracle for unknown factor-base logs. Recovery uses a bounded shifted
target fiber and verifies the returned scalar by independent group replay.

## Success, stop conditions and accounting

Success requires zero accepted invalid certificates, exact norm checks,
factor-base log replay, and exact recovery for the fixed correctness
controls. A success does not establish natural relation yield or scaling.
Stop when the field/curve gate fails, the pair budget is exhausted, the
matrix lacks rank, or the target-shift budget is exhausted; preserve the
failure status. Never fall back to rho, exhaustive log search or a planted
scalar to turn a failed IC cell into success.

Retain setup point count, usable distinct norm images before sign folding,
matrix columns, pair trials, duplicate lines, nonsplit residuals, valid
certificates, zero projected rows, independent rows, rank, anchor work,
target trials and scalar verification. They are distinct counts, not a
calibrated common operation unit. Set cold/online timing, total operations,
rho comparison and speedup to null. No wall-time comparison is run here;
the published same-field quartic algorithm's O-tilde(q) bound alone does
not improve the elliptic rho O(sqrt(r)) reference. A future performance
comparison must use the repository's full accounting and isolated runner.

## Delivery and remaining generalization

Expose the same native kernel through `cryptanalysis::bielliptic_quartic`
in both Rust crates and a dependency-free diagnostic command. Keep the
two source snapshots byte-identical and test each checkout. General
Jacobian target decomposition, a reduced factor base with large-prime
recombination, extension-field descent and a matched rho comparison are
separate, unimplemented stages and are never implied by a toy success.
