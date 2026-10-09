# Deferred balancing for XYZZ mixed addition

Retain the same U14 unit-orbit digit stream, affine table, and XYZZ formulas.
Change only the reduction schedule inside a generic mixed addition: carry
Montgomery quotients through the polynomial, balance `H` and `R` before the
zero tests, and balance the four output coordinates before the next addition.
Keep the existing balanced XYZZ implementation as an independent mode in the
same binary. The exceptional doubling and inverse branches follow the
existing implementation.

## Coefficient bounds

Let `R=2^128`; a balanced `Pair` coefficient has magnitude below `R`.
If two `Pair` inputs have coefficient magnitudes below `B_L R` and `B_R R`,
their raw Montgomery product has coefficient magnitude below
`4(B_L B_R+1)R`: the Eisenstein product has each coefficient below
`3 B_L B_R R²`, the Montgomery correction has each coefficient below
`3R²`, and the exact division by `R` gives the stated conservative bound.
Each input coefficient below `760R` fits three 64-bit limbs, and every
temporary product fits the eight-limb `Signed` magnitude. For
`balance_add_output`, multiplication by the conjugate of `pi` yields each
coefficient below `4B R²` when its input bound is `BR`; the largest output
bound below gives `4B < 3040`, well below its `2^26` high-word limit.

| Stage | Input bound units of `R` | Raw output bound units of `R` |
| --- | ---: | ---: |
| `U=x₂ ZZ`, `S=y₂ ZZZ` | 1 and 1 | 8 each |
| `H=U-X`, `R'=S-Y` before balancing | 8 and 1 | 9 each |
| balanced `H`, `R'` | 9 | 1 each |
| `HH=H²` | 1 and 1 | 8 |
| `HHH=H HH`, `V=X HH` | 1 and 8 | 36 each |
| `R'²` | 1 and 1 | 8 |
| `X'=R'²-HHH-2V` | 8, 36, 72 | 116 |
| `V-X'` | 36, 116 | 152 |
| `R'(V-X')` | 1 and 152 | 612 |
| `Y HHH` | 1 and 36 | 148 |
| `Y'=R'(V-X')-Y HHH` | 612 and 148 | 760 |
| `ZZ'=ZZ HH` | 1 and 8 | 36 |
| `ZZZ'=ZZZ HHH` | 1 and 36 | 148 |

This table supplies bounds to the existing checked rectangular products and
`balance_add_output`. A failed limb or correction assertion is a correctness
failure, not a candidate timing result.

## Frozen correctness panel

Build the release binary offline. Recheck every scalar in the existing
129-case secp256k1 fixture against its independently supplied point, plus
`0`, `1`, the subgroup order `n`, and `n+1`. Generate 512 additional
256-bit scalars as `SHA256("xyzz-deferred-v1:" || i_be32) mod n` for
`i=0..511`. Compare the deferred and balanced XYZZ modes on every scalar,
including their selected representative and generic-addition count. Compare
the fixture outputs to the upstream Jacobian mode on the same points. Preserve
the exact input, source, executable, and output hashes and all raw output.
Check the single-case benchmark dispatch for Jacobian, balanced XYZZ, and
deferred XYZZ against the fixture, with matching preparation and online
interval boundaries. Local wall times are diagnostic only under the repository CPU
isolation gate. Make a paired timing claim only after a strict host preflight
and the full same-binary, alternating-order panel.
