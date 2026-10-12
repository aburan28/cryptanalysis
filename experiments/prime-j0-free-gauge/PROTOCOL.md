# Unit-steered τ in Jacobian coordinates

## Frozen hypothesis and proof obligation

For `E: y²=x³+b` over a field with a primitive cube root `beta`, let
`phi(x,y)=(beta*x,y)` and `tau=1-phi`. The current Jacobian τ formula
produces `(X',Y',Z')` with `Z'=(1-beta)*X*Z`. Replace only its final
constant by `beta^delta*(1-beta)`, for `delta` in `{0,1,2}`. The output
is `(X',Y',beta^delta*Z')`; it represents

`(X'/(beta^(2delta)*Z'^2), Y'/(beta^(3delta)*Z'^3))
 = (beta^delta*x(tau(P)), y(tau(P))) = phi^delta(tau(P))`.

The equality uses `beta³=1`. The arithmetic still performs one
Montgomery multiplication by a selected constant in the Z update; the
three constants are formed from `1`, `beta`, and `beta²` with field
additions. Since `tau` commutes with `phi`, a τ step can change the
unit orientation of the partial accumulator with no extra field
multiplication. The initial orientation is free at the identity.

Add an opt-in `paired2-free-gauge` arm. Keep the exact two-neighbor
lattice representatives, selected streams, 18 prepared seed points,
τ count, and mixed-add count of `paired2`. At each nonempty digit
position choose the orientation that minimizes digit-coordinate
rotations. At the last nonempty position also charge a possible final
inverse-unit correction. A frozen 12-by-2 choice table covers the one-
and two-digit power patterns; an independent unit test recomputes all
24 entries. Count every selected τ constant change, digit rotation,
final correction, and output inversion. Verify outputs against generic
group arithmetic on both study curves, including zero/order boundaries,
identity, equal/opposite points, and cancellation.

This is a variable-time research path for public scalars. The isogeny
formula and symmetric unit digit sets have prior literature; academic
novelty of this coordinate steering is unproved. The simple operation
model excludes recoding, branching, and table lookups.

## Held-out stage gate

Earlier scalar panels may be used for development only. Commit this
protocol, implementation, unit tests, independent affine fixture
generator, and serial checker before creating fresh 1,024-pair inputs
on each curve. Freeze their bytes and output digests in a second commit
before any τ arm sees them. Evaluate `joint,paired2,paired2-trellis,
paired2-free-gauge,paired2-free-gauge,paired2-trellis,paired2,joint`
serially. Keep every raw trial, failure, source and binary hash, point
operation count, coordinate-rotation breakdown, free gauge changes,
and correctness replay. Same-stream pairing with `paired2` and the
trellis control is mandatory.

The batch is an algorithmic scalar-stage diagnostic, not the default
one-target rho metric. A later fresh public one-target rho solve, with
all target-dependent preparation, batch normalization, restarts, and
verification charged, is required to assess the end-to-end path. CPU
speedup requires a host-level isolation receipt under AGENTS.md; local
timings from an unverified host remain exploratory.
