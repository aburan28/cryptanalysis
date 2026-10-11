# Fused direct-index record for scalar digits and point choices

The [direct 2-adic index](../prime-j0-adic-orbit-20261011/PROOF.md)
maps each radix-1024 residue pair to a unique six-unit class index and
a unit `u_k` that maps the query residue to the canonical residue.
The original three-byte class code records a seed `s`, tau exponent
`e`, and unit `u_j`; its canonical signed digit is

`d_c = u_j(tau^e s)`.

Store that signed digit alongside the code in an eight-byte aligned
record: a little-endian `u32` code followed by two little-endian
signed `i16` coordinates. The full atlas retains its seed array for
building the fixed-generator point tables. At scalar evaluation,
decode the record at the direct class index and compute the digit as

`d = u_k^(-1)(d_c)`.

The point-table choice still uses `s`, `e`, and the composed unit
`u_k^(-1)u_j`. Since the units commute with tau and preserve the
Eisenstein norm, this fused decoder returns the same signed digit and
same point choice as the three-byte direct-index decoder. In
particular, `d` has the query residue modulo 1024 and satisfies the
same norm bound `N(d)<=1024^2`. Subtracting `d` then dividing the
scalar coefficients by 1024 is exact.

The old runtime decoder loads a seed pair, applies tau zero to two
times, and selects a unit image to reconstruct each full digit. The
fused decoder loads one class record and applies only the inverse
canonicalizing unit to its stored digit. Both still compute the
2-adic class index and the unit code needed for the point table.

The record array costs `8*174,764 = 1,398,112` bytes. With a 16-byte
header and `4*83,051 = 332,204` seed bytes, the full atlas is
**1,730,332 bytes**. This adds 873,820 bytes over the three-byte
direct-index atlas. Using its measured native retained size of
65,596,552 bytes gives a projected fused size of 66,470,372 bytes,
638,492 bytes below a nominal 64 MiB capacity. Native allocation
accounting must verify the actual size.
