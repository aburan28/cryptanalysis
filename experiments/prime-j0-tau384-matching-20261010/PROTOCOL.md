# Two-bucket radix-384 tau matching format

This experiment constructs a fifteen-window fixed-generator secp256k1
scalar format in the Eisenstein ring. It keeps the exact radix-384 recoding
and certified representative of mode 134, but replaces the six-unit orbit
table with seeds that also cover one admissible image under the norm-three
endomorphism `tau`. Online evaluation sums the exponent-zero and
exponent-one selections separately and computes `B0 + tau(B1)`.

## Frozen construction

- Use the secp256k1 subgroup order and the existing certified Eisenstein
  representative. Coordinates are pairs `(a,b)` with
  `N(a,b)=a²+3ab+3b²`, `omega(a,b)=(a+3b,-a-2b)`, and
  `tau(a,b)=(-3b,a+3b)`. Unit images are `d,-d,omega(d),-omega(d),
  omega²(d),-omega²(d)` in that order.
- Set radix `R=384`, window count `W=15`, and maximum digit length `D=253`.
  For each of the `R²` residue pairs, take the least row-major residue in
  its six-unit orbit as its canonical class. Choose each class's direct
  digit by the existing four-corner nearest-digit rule, minimizing
  `(norm,a,b)` lexicographically.
- Add a directed edge from class `s` to the class of `tau(d_s)` when the
  target differs from `s` and `3*N(d_s) <= D²`. The undirected edge means
  one stored seed can cover both classes. Assert that this finite graph is
  a forest, then compute an exact maximum-cardinality matching by tree DP.
  Break equal-score choices by ascending canonical class ID. For an edge
  admissible in both directions, store the smaller-ID source.
- Store one direct seed for each unmatched class and one source seed for
  each matched edge. For each residue, encode seed index, tau exponent
  `0` or `1`, and the unit image code. Exhaustively check unique residue
  reconstruction and `N(digit) <= D²` before writing the atlas.
- Store a 32-bit code per residue, signed 16-bit seed coordinates, and
  one 64-byte affine point per seed per window. Retained bytes include the
  code array, seed array, table rows, and Rust container metadata.

## Proof and validation gates

The certified representative has norm at most `n/3`. With
`G=(R^W-1)/(R-1)`, require `n < 3*(R^W-D*G)^2`; this makes the final
quotient zero for every subgroup scalar. Check this inequality with exact
integers, and check that it fails for `D=254` under the same bound.

Freeze the construction source before drawing the new scalar panel. Use
seed `20261010136` and 4,096 unique full-range reduced scalars disjoint
from previous panels. Reconstruct every scalar exactly, compare the native
point result with mode 134, check the first 128 with independent binary
multiplication, verify all 129 fixed fixture cases, and run the complete
release test suite. Preserve source, input, atlas, binary, command, and
failure receipts. A Linux correctness replay may use the existing RunPod
serial queue; it is not a controlled timing environment.

The future online comparison pairs both modes on the same public scalar,
binary, and isolated host. Charge scalar reduction, representative choice,
all recoding, table traffic, both bucket sums, the tau map, projective
merge, final inversion, and verification. Do not promote a CPU speedup
without the host-level receipt required by `docs/ISOLATED_BENCHMARKS.md`.
