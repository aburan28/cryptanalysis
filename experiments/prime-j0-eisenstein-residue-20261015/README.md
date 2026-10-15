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
These are exact correctness screens. The conversion-free
[native field and curve kernel](eisenstein_pair_native.rs) implements pair
addition, subtraction, rotation, three-product multiplication, 33-byte
pack/unpack, Jacobian doubling, mixed addition, and binary scalar
multiplication. The source SHA-256 is
`b47b200bbbca7c731bff22854f37967d7cda8e9ba9b37db58ce6c7969905dcf6`;
the x86-64 Linux release binary SHA-256 is
`bdd612d844c40852f32742601ca02d9c0cd73837d72f08da9b0fa5b87072a543`.
On RunPod it verified every result from the frozen 12,288-scalar fixture by
comparing projective coordinates against independently computed affine
points, and round-tripped both packed affine coordinates for every case.
The full replay recorded `54,846.381069 ms` for the Solinas-reduced binary
scalar stream. This full replay is a correctness and implementation-cost
diagnostic; the separate paired CPU panel below supplies its timing gate.

The field reducer originally used two arbitrary-precision divisions per
operation. For `p=2^256-c`, `c=2^32+977`, let `q₀` be the arithmetic
256-bit shift of the centered numerator and `low` its nonnegative low
256 bits. The exact remainder relative to `p` is `low+q₀c`. When
`|q₀c|<p-c`, this remainder lies in `(-p,2p)`, so one branch correction
produces the exact quotient. The native kernel retains both the division
and this shift-and-correction path in one executable. The frozen
[Tier 1 panel](tier1-eisenstein-reducer-cpu40-manifest.json) pairs them on
the first 128 unique scalars of the same fixture, with 16 alternating
repetitions and adjacent A/A gates from the
[predeclared rules](tier1-eisenstein-reducer-cpu40-rules.json). Its RunPod
job is `16ad0015d96b497ca15cc3de3ce090e6`.

The completed [panel](16ad0015d96b497ca15cc3de3ce090e6/summary.json)
contains 96 valid arms and all 48 planned pairs, with stable artifacts.
Every adjacent A/A ratio passed `[0.90,1.11]`. The
[audit](tier1-eisenstein-reducer-cpu40-audit.json) matched every raw output,
stderr file, source/binary/fixture hash, case order, and pair to the
manifest; it also checked the full correctness replay in the
[provenance archive](eisenstein-pair-native-provenance.tar.gz). The raw
[result archive](16ad0015d96b497ca15cc3de3ce090e6.tar.gz) has SHA-256
`8f348881ae400a0e14eefc960935afab08f7520ee82361af8464587f3383c0c7`;
the provenance archive has SHA-256
`9f963999a6d43ab489ac872f118ed218ba355d8ea20519aac7a36e03bf1ddce7`.

| Tier 1 same-input binary scalar stream, 128 outputs | General division | Solinas shift and correction |
| --- | ---: | ---: |
| Mean timed multiplication | 593.263493 ms | 572.856894 ms |
| Mean time per scalar | 4.634871 ms | 4.475445 ms |

The median paired division/Solinas ratio is **1.037568×** across 16
comparison pairs, with a predeclared paired bootstrap 95% interval of
`[1.028125,1.046558]`. The result qualifies the reducer change for this
BigInt pair-field binary multiplier on the observed Tier 1 cloud instance.
The measured scope is the 128-scalar binary multiplier. The existing
radix-14 four-layer pipeline uses fixed-width field arithmetic; this
prototype's hundreds of milliseconds per 128 scalars identify
arbitrary-precision allocation and reduction as the next cost center to
remove before integrating the pair format.

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
| One exact quotient correction for a pseudo-Mersenne prime under the asserted correction bound | `solinas_one_correction` | Checked; Lean foundations `propext`, `Classical.choice`, `Quot.sound` |
| Full quotient-ring isomorphism, multiplication preservation, and rounding bounds | — | Formalization partial; a concrete `Z[ω]` quotient-ring definition and the map's kernel/index bridge remain open |

The next implementation step is a fixed-width pair-field reducer and
packed affine table integrated into the same radix-14, four-layer scalar
pipeline as the ordinary and two-x variants. That comparison must charge
packing/unpacking and all online field operations while preserving the
same-point fixture and Tier 1 gates.
