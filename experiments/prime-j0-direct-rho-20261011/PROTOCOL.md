# Direct norm-seven endomorphism in XYZZ coordinates

The fixed-seed priority cover has four buckets for `1`, `tau`, `tau^2`,
and `rho=1+tau`. Its folded evaluator adds the `rho` bucket to two other
buckets before applying `tau`. This experiment evaluates `rho` directly on
the XYZZ bucket and merges it once at the end.

For `P=(X,Y,ZZ,ZZZ)`, with affine coordinates `X/ZZ` and `Y/ZZZ`, let
`A=3X^3`, `B=4Y^2`, `C=beta*A`, `D=beta*B`, and
`E=2A-B+C-D`. Proposition 3.2 of the supplied paper gives polynomial
factors `F` and `H` such that Jacobian `rho(P)` is `(X*F,Y*H,Z*E)`.
In XYZZ coordinates the corresponding output is
`(X*F,Y*H,ZZ*E^2,ZZZ*E^3)`. The input and output scale identities are
`ZZ^3=ZZZ^2`; this transformation preserves the identity. The implementation
uses the existing fixed-constant Solinas multiplication for `beta*A` and
`beta*B` and ordinary Montgomery field operations for the other products.

First compare the direct variant with the folded priority evaluator and
independent group controls on the already observed 4,096-scalar panel. This
is a correctness diagnostic. If it passes, freeze a new disjoint scalar
panel before using it for any comparative operation or timing result. Keep
the same cover, atlas, input law, table bytes, and generated Rust source
outside this arithmetic change. Host-isolated paired timing is required for
a CPU performance claim.
