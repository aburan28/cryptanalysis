# Proof map for radix-152 axis factorization

The nearest four-corner digit satisfies `3Q(d) <= 152^2` for every
Eisenstein integer pair. For the pinned nearest secp256k1 representative,
`3Q(z) <= n < 2^256`. After sixteen steps,

`z = sum(i=0..15) 152^i d_i + 152^16 t`.

The norm triangle inequality gives

`152^32 * 3Q(t) <= (2^128 + sum(j=1..16) 152^j)^2`.

Exact integer arithmetic bounds the right side strictly below
`17,574,892 * 152^32`, hence `3Q(t) <= 17,574,891`.
Every nonzero six-unit orbit has exactly one image in the half-open
sector `(-u,b)` with `u <= 3b < 2u`. The identity

`12Q(-u,b) = 9(2b-u)^2 + 3u^2`

implies `u <= 4,840`; the sector inequalities then imply
`1 <= b <= 3,226`. Applying the inverse unit code to
`(-u,0)+(0,b)` reconstructs `t`. Addition and unit action commute
with the Eisenstein scalar map into the curve subgroup.

| Result | Lean declaration | Verification |
| --- | --- | --- |
| Four-corner digit bound | `PrimeJ0Axis152DigitCover.nearest_digit_bound` | Built for every integer pair |
| Sixteen-step terminal bound | `PrimeJ0Axis152TopBound.sixteen_steps_top_bound` | Built under the stated digit and initial norm bounds |
| Scalar reconstruction and congruence | `scalar_recode_reconstruct`, `scalar_recode_congruence` | Built for every scalar under the pinned representative |
| Unique unit sector | `PrimeJ0Axis152TopRank.unique_sector_image` | Built for each nonzero pair |
| Axis factorization and limits | `PrimeJ0Axis152TopRank.axis_factorization` | Built for every terminal pair within the cap |

`check.py` pins Lean 4.34.1, builds the stated theorem modules and their
pinned dependencies, rejects proof holes and research axioms, and checks
each `#print axioms` line. The recorded standard foundations are
`propext`, `Classical.choice`, and `Quot.sound`.

For integer radix `B >= 2`, the specified table's entry count is

`F(B) = 16 * (B^2 + gcd(2,B)^2 + 2gcd(3,B) + 2)/6 + U(B) + H(B)`, where

`C(B) = floor((2^128 + sum(j=1..16) B^j)^2 / B^32)`,
`U(B) = floor(sqrt(4C(B)/3))`, and
`H(B) = floor((2U(B)-1)/3)`.

Burnside's formula counts the six-unit residue orbits, including fixed
residues for even and divisible-by-three radices. `search.py` separately
enumerates all `152^2 = 23,104` residues and matches 3,852 orbits. The
radius ratio `2^128/B^16 + sum(k=0..15) B^(-k)` decreases with `B`.
For `B <= 130`, the two axis tables alone require at least 98,416
entries. For `B >= 162`, the sixteen ordinary tables alone require at
least 69,984 entries. Exact integer evaluation for the 33 remaining
radices finds the unique minimum `F(152)=69,698`; radix 153 is next at
69,711. The finite orbit cardinality and 33-radix census remain open
Lean bridges; the executable exact audit retains each integer row.
