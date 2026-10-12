# Proof map for the axis-factorized radix-416 format

The nearest four-corner digit obeys `3Q(d)≤416²`. For the pinned nearest
secp256k1 representative, `3Q(z)≤n<2²⁵⁶`. After thirteen steps,
`z=D+416¹³t` with `D=Σ(i=0..12)416ⁱdᵢ`. The norm triangle inequality gives

`416²⁶·3Q(t) ≤ (2¹²⁸ + Σ(j=1..13)416ʲ)²`.

Exact integer arithmetic places the right side below
`927429455·416²⁶`, so `3Q(t)≤927429454`. The six-unit orbit has one image
in the half-open sector `(-u,b)` with `u≤3b<2u`. The identity

`12Q(-u,b)=9(2b-u)²+3u²`

gives `u≤35164`; sector inequalities then give `1≤b≤23442`.
For nonzero `t`, choose the inverse unit code of the canonical image.
The terminal identity is

`t=unit^code((-u,0)+(0,b))`.

Both terminal axis tables therefore cover every scalar without
enumerating the terminal lattice. The algebraic scalar map from the
Eisenstein pair to the subgroup sends addition to point addition, and the
recorded unit code to its curve endomorphism. `DigitCover.lean` proves the
integer reconstruction and subgroup congruence. The Lean development
formalizes the pair-level sector and factorization; an independent curve
point replay is the next implementation gate.

| Result | Lean declaration | Exact status |
| --- | --- | --- |
| Four-corner digit coverage | `PrimeJ0Axis416DigitCover.nearest_digit_bound` | Checked for every integer pair |
| Thirteen-step terminal cap | `PrimeJ0Axis416TopBound.thirteen_steps_top_bound` | Checked under digit and initial norm hypotheses |
| Scalar reconstruction and congruence | `scalar_recode_reconstruct`, `scalar_recode_congruence` | Checked for every scalar under pinned representative |
| Unique six-unit sector | `PrimeJ0Axis416TopRank.unique_sector_image` | Checked for nonzero integer pairs |
| Axis factorization and coordinate limits | `PrimeJ0Axis416TopRank.axis_factorization` | Checked for all nonzero terminal pairs within cap |

`check.py` pins Lean 4.34.1, builds the actual modules and pinned
dependencies, rejects proof holes and custom axioms, and audits every
reported theorem with `#print axioms`. The allowed standard foundations
are `propext`, `Classical.choice`, and `Quot.sound`.

The exact point-entry function for integer radix `B≥2` is

`F(B)=13·(B²+gcd(2,B)²+2gcd(3,B)+2)/6+U(B)+H(B)`, where

`C(B)=floor(((2¹²⁸+Σ(j=1..13)Bʲ)/B¹³)²)`,
`U(B)=floor(sqrt(4C(B)/3))`, and
`H(B)=floor((2U(B)-1)/3)`.

Burnside's lemma gives the ordinary orbit formula, including fixed
residues for even and divisible-by-three radices. `search.py` directly
enumerates all 416² residues to audit the chosen even-radix count. The
radius ratio equals `2¹²⁸/B¹³+Σ(k=0..12)B⁻ᵏ`, which decreases with `B`.
For `B≤350`, the terminal-axis count is at least its value at 350,
553,698, above `F(416)=433,578`. For `B≥450`, the ordinary tables alone
have at least `13·450²/6=438,750` entries. Exact integer evaluation of
the remaining 101 radices gives unique minimum 416; radix 417 is second
with 433,585 entries. The global finite census and Burnside calculation
are verified by `search.py`; their Lean formalization is open at the exact
finite-cardinality and 101-radix certificate bridge.
