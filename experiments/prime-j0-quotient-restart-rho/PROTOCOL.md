# Quotient-valued scalar output at rho restarts

## Frozen identity and test

For the `j=0` curve, rho's order-six automorphism is
`psi(x,y)=(beta*x,-y)`. Thus `psi^4(x,y)=(beta*x,y)`. The opt-in
scalar evaluator omits its final unit correction and returns
`R=psi^(4g)(aG+bQ)` with a gauge tag `g` in `{0,1,2}`. At a rho
restart, the existing class reducer maps `R` to `psi^k R`.
The coefficients therefore need the **single** multiplier
`lambda^((k+4g) mod 6)` already used for class reduction. No second
scalar multiplication of the coefficients is needed. The table
points stay exact and use the existing eight-output batch evaluator.

The output point, transported coefficients, restart states, walk,
distinguished-point table, collision, and recovered scalar must match
the regular free-gauge path for the same public target and seed. The
candidate may choose its final gauge without charging a coordinate
correction. Its point work must keep the same τ, mixed-add,
preparation, and inversion counts, with no more rotations.

This construction is a quotient-valued scalar-output format for a
consumer that immediately canonicalizes the automorphism orbit.
It is not a replacement for exact scalar multiplication when the
caller needs the original point; the gauge tag is part of the output.
Unit tests verify the relation to generic group arithmetic for edge
and random scalar pairs on both study curves, including batch output.
Existing work on rho automorphism quotients includes
[Bernstein, Lange, and Schwabe's negation-map analysis](https://cr.yp.to/elliptic/negation-20110102.pdf).
Academic novelty of this specific combined format is unproved.

## One-target gate

Commit the implementation, tests, independent affine fixture
generator, checker, strict isolation manifest generator, and this
protocol before generating a fresh public target. Commit the target
in a separate second commit before any candidate solve. Run generic
reference, regular free-gauge batch, quotient-restart batch,
quotient-restart batch, regular free-gauge batch, generic reference
serially in Release and UBSan. Each invocation starts with an empty
rho table. Preserve raw successes, failures, hashes, operation counts,
online intervals, replay timing, and correctness certificate.

The online interval starts at target-dependent solve work after
input/subgroup validation and ends after internally verified scalar
recovery. It includes target-dependent preparation, batch table,
restarts, walk, collision, and failed work; process launch and fixture
generation are outside it. A separate post-solve scalar replay is
recorded. Local CPU timing remains exploratory until a qualifying
host-level isolation receipt is available. Keep `cpu_speedup_claim`
and `isolation_receipt` null until then; do not enable automatic
routing from this gate.
