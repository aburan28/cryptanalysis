# A 33-byte Eisenstein residue x coordinate

The secp256k1 prime splits in the Eisenstein integers. An exact norm-
`p` element

`π = -367917413016453100223835821029139468249
     -64502973549206556628585045361533709078·ω`

defines `F_p ≅ Z[ω]/(π)`, where `ω²+ω+1=0`. Map a pair `(u,v)` to
`u+vβ mod p`, with
`β=0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee`.
The exact computations give `N(π)=p`, `π(β)=0 mod p`, and
`β²+β+1=0 mod p`. The map is onto because integer pairs `(u,0)` reach every
residue. The ideal `(π)` has index `N(π)=p`, so it equals the map's kernel.
This supplies a two-coordinate field representation with order-three
rotation

`ω·(u+vω) = -v + (u-v)ω`.

Rotation uses integer additions and subtraction, with no 256-bit constant
field multiplication. General multiplication uses three approximately
129-bit products: for `A=us`, `B=vt`, and `C=(u+v)(s+t)`, the unreduced
product is `(A-B, C-A-2B)`. The
[exact prototype](eisenstein_residue.py) subtracts rounded multiples of the
ideal basis `π=(a,b)` and `ωπ=(-b,a-b)`; their determinant is `p`, so this
reduction preserves the field residue. Its current Python reduction uses
exact large-integer division. The native cost of that division and the
field-to-coordinate conversion must be measured before routing scalar
multiplication through this format.

Rounding the inverse-basis coordinates puts each error in `[-1/2,1/2]`.
Consequently, the reduced first coordinate has magnitude at most
`(|a|+|b|)/2`, and the second at most `(|b|+|a-b|)/2`. Both sums are strictly
below `2^129`, so each magnitude is below `2^128`. Two sign-and-128-bit-
magnitude coordinates pack into **258 bits, or 33 bytes**. Coupled with a
32-byte affine y coordinate, the packed point payload is **65 bytes**;
the current two-x table entry is 96 bytes. A plain pair of signed 128-bit
integers is insufficient: 1,984 of 20,000 reduced pairs examined by
the 10,000-case check had at least one coordinate outside its signed range.
The prototype performs actual 33-byte pack/unpack round trips.

The [10,000-pair receipt](self-check-10000.json) checks conversion,
addition, one and two rotations, multiplication, reduction idempotence,
and pack/unpack against ordinary `F_p` arithmetic. Every comparison passed;
the maximum observed absolute coordinate length was 128 bits. The
[1,000-pair receipt](self-check.json) is a smaller bounded screen.
These are exact correctness screens, with native cost recorded as
`unmeasured`.

## Proof map

The pinned Lean 4.34.1 module
[EisensteinResidue.lean](EisensteinResidue.lean) was built with
`lean EisensteinResidue.lean`; the [output](lean-check.log) records
`#print axioms` for each declaration.

| Result | Lean declaration | Status |
| --- | --- | --- |
| Three successive coordinate rotations return the pair | `rotate_three` | Checked; Lean foundations `propext`, `Classical.choice`, `Quot.sound` |
| `N(π)=p` | `pi_norm_eq_prime` | Checked; no axioms |
| `β²+β+1=0 mod p` | `beta_cubic` | Checked; no axioms |
| `π(β)=0 mod p` | `pi_in_kernel` | Checked; no axioms |
| Both ideal-basis widths are below `2^129` | `basis_x_width`, `basis_y_width` | Checked; no axioms |
| Full quotient-ring isomorphism, multiplication preservation, and rounding bounds | — | Formalization partial; a concrete `Z[ω]` quotient-ring definition and the map's kernel/index bridge remain open |

The next native falsifier is a packed 33-byte x table with exact conversion
and field operations, checked against the frozen uniform-derived scalar
fixture. Its full scalar-batch interval must charge packing/unpacking and
coordinate conversion as they occur online, and compare against ordinary
affine-layer and the 96-byte two-x table under the same Tier 1 runner.
