# Proof map for the radix-929 bounded top-state format

The readable proof uses the quadratic norm `Q(a,b)=a²+3ab+3b²` on the
Eisenstein coordinate pair. Let `z = d₀ + 929d₁ + ... + 929¹¹d₁₁ +
929¹²t`. The nearest four-corner chooser yields `3Q(dᵢ) ≤ 929²`.
The nearest initial representative satisfies `3Q(z) ≤ n`. The norm triangle
bound gives `3Q(t)·929²⁴ ≤ (initialRadius + radius929(12))²`.
The exact integer certificate in `TopBound.lean` bounds the right side
strictly below `679763·929²⁴`, so integrality gives `3Q(t) ≤ 679762`.
Reconstruction followed by the lattice congruence gives the original scalar
modulo the secp256k1 subgroup order.

The six unit transforms preserve the norm. The half-open sector
`a<0`, `-a≤3b`, `3b<-2a` contains exactly one image of each nonzero orbit.
Writing the canonical pair as `(-u,b)` gives the exact row identity
`12Q(-u,b)=9(2b-u)²+3u²` and hence `u≤952` under the top bound. For each
row, `topball.py` computes the exact inclusive range from this identity and
checks all 821,953 states and all 136,993 ranks.

| Result | Lean declaration | Exact hypotheses | Verification |
| --- | --- | --- | --- |
| Twelve-step residual bound | `PrimeJ0Radix929TopBound.twelve_steps_top_bound` | Twelve valid radix steps, initial `3Q≤n`, each digit `3Q≤929²` | Lean 4.34.1 checked |
| Four-corner digit bound | `PrimeJ0Radix929DigitCover.nearest_digit_bound` | Any integer coordinate pair | Lean 4.34.1 checked |
| Scalar bound and congruence | `scalar_top_bound`, `scalar_recode_congruence` in `PrimeJ0Radix929DigitCover` | Any integer scalar, pinned secp256k1 constants and representative chooser | Lean 4.34.1 checked |
| Unique top orbit sector | `PrimeJ0Radix929TopRank.unique_sector_image` | Any nonzero integer pair | Lean 4.34.1 checked |
| Row identity and finite row bound | `top_row_identity`, `top_row_limit` in `PrimeJ0Radix929TopRank` | `3Q≤679762`, nonnegative row | Lean 4.34.1 checked |
| Arithmetic rank and exact orbit count | `topball.py` exhaustive audit | All integral pairs in the bounded ball | Exhaustive Python replay; not yet a Lean theorem |

`check.py --check` pins `leanprover/lean4:v4.34.1`, builds the actual modules,
hashes every new and imported source, and compares all `#print axioms`
lines to `lean-build.txt`. The only allowed foundation axioms are `propext`,
`Classical.choice`, and `Quot.sound`. The checker rejects `sorry`, `admit`,
`sorryAx`, and custom `axiom` tokens. `lean4checker --fresh` may be run on a
host that supplies it; the pinned Lean build and axiom audit are the
reproducible check here.
