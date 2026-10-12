# Two-level Karatsuba product proof

For any radix `B`, write `A = a0 + B*a1` and `D = b0 + B*b1`. Set
`p0 = a0*b0`, `p2 = a1*b1`, and
`d = (a1-a0)*(b0-b1)`. Then

`A*D = p0 + B*(p0+p2+d) + B²*p2`.

The middle coefficient is exactly `a0*b1+a1*b0`, so the formula is the
ordinary full product. At the first level `B=2^128`. Each of its three
128-bit products uses the same formula at `B=2^64`; therefore the full
256-bit wide product needs nine 64-by-64 products. The Rust implementation
computes the magnitudes of the two differences and applies their combined
sign with a mask through fixed-length carry chains.

## Lean proof map

[`KaratsubaProduct.lean`](KaratsubaProduct.lean) builds with the pinned
[`lean-toolchain`](lean-toolchain) using `import Lean`.

| Result | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| Two-limb product identity | `PrimeJ0Karatsuba.two_limb_product` | Arbitrary integer radix and limbs | Checked |
| Middle coefficient identity | `PrimeJ0Karatsuba.middle_coefficient` | Arbitrary integer limbs | Checked |
| Four-limb structural composition | `PrimeJ0Karatsuba.four_limb_product` | Arbitrary integer radix and limbs | Checked |

Run `ELAN_TOOLCHAIN=leanprover/lean4:v4.34.1 lean KaratsubaProduct.lean`
from this directory. The retained [`lean-build.txt`](lean-build.txt) records
`#print axioms`: the declarations use only `propext` and `Quot.sound`.
The source has no `sorry`, `admit`, custom research axiom, or unchecked
native evaluation. `lean4checker --fresh` was unavailable on this host.

The Lean identities prove the unbounded integer product composition. The
bit-level correspondence of the Rust mask, wrapping subtraction, and carry
assembly to those identities is not formalized. The independent 512-bit
product test checks that implementation bridge. Canonical reduction after
the wide product is covered by the separate checked theorem in
`../prime-j0-u14-solinas-20261012/SolinasReduction.lean` and by field tests.
