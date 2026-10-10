# Hybrid finalization of Eisenstein projective points

The candidate keeps the scalar decomposition, U14 table, unit actions,
and Jacobian point additions in the existing Eisenstein field kernel.
At the final projective point only, it maps `X`, `Y`, and `Z` to a
conventional four-limb secp256k1 field, computes the affine inverse
there, and emits canonical hexadecimal coordinates. The parent fixed-
limb selector and point path are shared by both modes.

Let `R=2^128`, `R'=2^256`, and let `beta` be the selected root of
`beta^2+beta+1=0 (mod p)`. The balanced Eisenstein Montgomery pair
`(a,b)` represents the field element `z` through

`a+b*beta = z*R (mod p)`.

An ordinary four-limb Montgomery element represents `z*R'`. Hence the
cross-representation map is

`z*R' = a*R + b*beta*R (mod p)`.

Precompute `R` and `beta*R` in the ordinary Montgomery domain. Each
signed coefficient has magnitude below `2^128`; multiply its magnitude
by the corresponding precomputed constant, apply its sign modulo `p`,
and add the two terms. The constants and ordinary Montgomery context
are prepared before the online interval. For a nonidentity Jacobian
point, compute `z_inv=z^(p-2)`, then `x=X*z_inv^2` and
`y=Y*z_inv^3` entirely in the ordinary Montgomery field. Convert only
the final two canonical field elements to hexadecimal.

The parent field-inversion chain uses 257 squares and 14 other products.
This candidate runs that same exponent in four-limb arithmetic after
six fixed-constant conversion products for `X`, `Y`, and `Z`. The final
point and scalar output contract remain unchanged. A complete online
CPU benefit must be measured; source operation counts and local timings
alone do not establish one.

## Frozen gates

1. Commit this protocol before generating a new disjoint 4,096-scalar
   holdout. Use the prior fixed-limb holdout as design data. Check the
   conversion identity on coefficient boundaries and at least 256
   deterministic field pairs against the independent BigInt mapping.
2. Compare both finalizers on every boundary, prior, and new holdout
   point. Independently replay at least 128 new points with binary
   scalar multiplication. Check all 129 frozen fixture points, zero
   and nonidentity cases, and the full native release suite.
3. Retain source, input, binary, raw output, exit, and compiler hashes.
   A paired same-binary online panel must charge scalar reduction,
   recoding, table lookup, point work, representation conversion,
   inversion, affine formatting, and correctness verification. Promote
   a wall-time improvement only on a host passing the repository's
   isolation and noise gates.

This is a representation-switching finalizer for the existing U14
scheme. The underlying Montgomery arithmetic and GLV endomorphism have
prior art; a priority claim for the combination needs separate review.
