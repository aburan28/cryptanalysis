# Square-based Z update for unit-steered τ

## Frozen hypothesis

The Xu--Yu--Han--Lu τ formula supplies a square-based Jacobian Z update.
For the selected unit-steered constant `c=beta^delta*(1-beta)`, compute

`c*X*Z = Z*((X+c)^2 - X^2 - c^2)/2`.

`X^2` is already needed for the τ X coordinate. The alternate update
therefore replaces the original field multiplication `c*X` with one
field squaring and field additions, followed by a modular half. The
three values of `c²` are `-3*beta`, `-3`, and `-3*beta²`, formed from
prepared constants with field additions. For an odd field modulus,
halving a residue `t` is `t/2` when even and `(t+p)/2` when odd; the
implementation uses a no-overflow equivalent. This is the paper's
known Z identity extended to the selected unit-steered constant, not
an independently novel isogeny formula.

Add an opt-in `paired2-free-gauge-square-z` scalar-stage arm. It must
retain the exact selected streams, τ steps, mixed additions, digit
rotations, gauge changes, final correction, prepared bytes, and
correctness digest of `paired2-free-gauge`. Count every alternate Z
step and require that count to equal the τ count. Unit tests compare
all outputs with both the regular steered arm and generic group
arithmetic on both study curves, including boundaries, identity,
equal/opposite points, cancellation, and random pairs.

## Held-out gate

Earlier scalar fixtures are for development only. Commit the
implementation, tests, protocol, fixture generator, and checker
before creating fresh 1,024-pair inputs on `glv-j0-32` and `j0-56`.
Freeze the input bytes and independent affine digests in a second
commit before evaluating either arm. Run regular, square Z, square Z,
regular serially on each curve. Preserve every raw trial and failure,
binary and source hashes, exact operation counters, output replay,
and local timings. Report the one-multiplication-for-one-square
substitution as a source-level model, not as a measured CPU win.

This batch is a scalar-stage diagnostic. A fresh one-target rho solve
on the same public point as a generic reference, followed by a
qualifying host-level isolation receipt, is required before a CPU
speedup or automatic routing claim. Academic novelty of the complete
unit-steered scheme remains unproved.
