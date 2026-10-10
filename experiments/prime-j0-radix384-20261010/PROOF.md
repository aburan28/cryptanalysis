# Exact radix-384 coverage and table size

The existing certified scalar map returns an Eisenstein integer `z` of
norm at most `n/3`, where `n` is the secp256k1 group order. At each step,
the nearest congruent digit `d_i` satisfies `||d_i|| <= 384/sqrt(3)`.
With `z_(i+1)=(z_i-d_i)/384`, induction gives

`z = sum_(i=0)^14 384^i d_i + 384^15 z_15`.

The triangle inequality bounds the final radius by

`||z_15|| <= sqrt(n/3)/384^15 + sum_(j=0)^14 384^(-j)/sqrt(3) < 1`.

The last strict inequality is checked using integers in
`check_algebra.py` as

`(ceil(sqrt(n)) + sum_(j=1)^15 384^j)^2 < 3*384^30`.

Every nonzero Eisenstein integer has norm at least one. Thus `z_15=0`,
and the fifteen selected points reconstruct the scalar multiple.

For residues modulo 384, Burnside's lemma gives fixed-point counts
`384^2, 4, 3, 3, 1, 1` for the identity, negation, two order-three
actions, and two order-six actions. Therefore each window has
`(384^2+12)/6 = 24,578` unit orbits. Fifteen windows contain 368,670
affine point slots or 23,594,880 point bytes at 64 bytes per point.
The atlas and window descriptors are charged separately by the
implementation. A nonzero digit is selected at most fifteen times,
requiring at most fourteen mixed additions; grouped unit gauges can
require at most two additional field products.
