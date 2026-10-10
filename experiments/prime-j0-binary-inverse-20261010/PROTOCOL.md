# Binary-GCD finalization after Eisenstein scalar multiplication

This candidate shares the mode-123 scalar decomposition, U14 table,
unit actions, and Eisenstein Jacobian point path. It maps the final
projective `X`, `Y`, and `Z` to the four-limb secp256k1 Montgomery field,
then replaces the `p-2` inversion chain with a binary extended-GCD
inverse. Affine recovery and hexadecimal output remain four-limb.

Let `R'=2^256`, and let the converted `Z` be `zR' (mod p)`. Binary GCD
on this stored residue returns `(zR')^-1 = z^-1(R')^-1 (mod p)` in
canonical form. Precompute `(R')^3 (mod p)` once. A Montgomery product
of the GCD inverse and `(R')^3` yields `z^-1 R' (mod p)`, which is the
required Montgomery representation of `z^-1`. This conversion needs
one Montgomery product after the GCD loop.

The binary algorithm maintains `u`, `v`, `x_u`, and `x_v` with
`x_u*(zR') = u (mod p)` and `x_v*(zR') = v (mod p)`. Initially
`(u,v,x_u,x_v)=(zR',p,1,0)`. For each even operand, halve it and halve
its coefficient modulo odd `p`. For odd operands, subtract the smaller
from the larger and subtract their coefficients modulo `p`. When an
operand reaches one, its coefficient is the inverse. A modular half of
an odd coefficient uses the full carry of `x+p` before shifting, so the
256-bit near-Mersenne modulus cannot lose its top bit.

The iteration count and branches depend on the input point. Keep this
mode opt-in for public-scalar research and do not route secret-scalar
operations through it. The comparison target is complete online scalar
multiplication through independently checked affine output, not only
field inversion in isolation.

## Frozen gates

1. Commit this protocol before generating a disjoint 4,096-scalar
   holdout. Preserve every previous panel and its source digest.
2. Check modular-halving boundary cases, the binary inverse against
   the parent Fermat-chain inverse on at least 512 deterministic
   nonzero field elements, and `a*a^-1=1 (mod p)` independently.
3. Compare complete mode-123 and mode-124 outputs on all boundary,
   prior-panel, and new-holdout points. Replay at least 128 new points
   through the independent binary scalar path. Check all 129 frozen
   fixture points and the full native release suite.
4. Record source, input, compiler, binary, raw output, test exit, and
   memory. A paired isolated panel must use the same binary, scalar,
   precomputed U14 table, resource envelope, and online interval,
   including finalization and correctness verification. A rejected
   host preflight or noise gate keeps the speedup unknown.
