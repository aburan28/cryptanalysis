# Proof map for the radix-569 bounded top-ball format

The nearest four-corner digit for each integer pair has
`3Q(d) ≤ 569²`, where `Q(a,b)=a²+3ab+3b²`. For the pinned secp256k1
nearest representative, `3Q(z) ≤ n < 2²⁵⁶`. Writing thirteen digits as
`D=Σ(i=0..12)569ⁱdᵢ` and `z=D+569¹³t`, the norm triangle bound gives

`569²⁶ · 3Q(t) ≤ (2¹²⁸ + Σ(j=1..13)569ʲ)²`.

The right side is strictly below `270667·569²⁶`; integrality gives
`3Q(t)≤270666`. Nonzero pairs in this ball have six distinct unit images.
The half-open sector `a<0`, `-a≤3b`, `3b<-2a` contains one image per orbit.
Writing its pair as `(-u,b)`, the identity
`12Q(-u,b)=9(2b-u)²+3u²` gives `u≤600`. The exact row bounds and rank
are checked for every one of the 327,235 pairs by `topball.py`.

| Mathematical result | Lean declaration | Hypotheses and status |
| --- | --- | --- |
| Four-corner digit bound | `PrimeJ0Radix569DigitCover.nearest_digit_bound` | Every integer pair; checked |
| Thirteen-step terminal bound | `PrimeJ0Radix569TopBound.thirteen_steps_top_bound` | Valid steps, initial `3Q≤n`, digits `3Q≤569²`; checked |
| Scalar reconstruction and congruence | `scalar_recode_reconstruct`, `scalar_recode_congruence` | Every integer scalar under pinned secp256k1 representative; checked |
| Unique terminal unit sector | `PrimeJ0Radix569TopRank.unique_sector_image` | Every nonzero integer pair; checked |
| Exact row identity and finite limit | `top_row_identity`, `top_row_limit` | `3Q≤270666`; checked |

`check.py` pins Lean 4.34.1, builds the imported representative modules
and all three new theorem modules, rejects unverified proof tokens, and
audits each `#print axioms` result. `lean-build.txt` binds the source hashes
and build output. The accepted foundations are `propext`,
`Classical.choice`, and `Quot.sound`. The Lean recoder proves the arithmetic
format for a four-corner chooser; the Python atlas checks its own tie
choices exhaustively.

For the finite radix census, the exact point-count formula follows from
`4(3Q(a,b))=3a²+9(a+2b)²` and counting integers `a+2b` with the parity of
`a`. Burnside gives the ordinary orbit count
`(B²+gcd(2,B)²+2gcd(3,B)+2)/6`; only zero is fixed by any nonidentity
unit on the integer terminal lattice, giving `(top_states+5)/6` top
orbits. `radix_search.py` evaluates these exact integer formulas on the
declared finite interval; the central universal coverage theorem is checked
in Lean.
