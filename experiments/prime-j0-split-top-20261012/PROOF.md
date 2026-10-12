# Proof map for the radix-671 split-top format

Let `Q(a,b)=a²+3ab+3b²`. A nearest radix-671 residue digit has
`3Q(d)≤671²`; the initial Eisenstein representative has `3Q(z)≤n` for the
pinned secp256k1 subgroup order. Writing twelve digits as
`D=Σ(i=0..11) 671^i d_i`, the norm triangle bound gives

`671^24 · 3Q(t) ≤ (2^128 + Σ(j=1..12) 671^j)^2`, where
`z=D+671^12 t`. The exact integer inequality

`(2^128 + Σ(j=1..12) 671^j)^2 < 1668628671 · 671^24`

implies `3Q(t)≤1668628670`. The two quadratic identities
`4Q(a,b)=a²+3(a+2b)²=(2a+3b)²+3b²` then give
`|a|≤47168` and `|b|≤27232`. Centered division by 256 gives
`t=ell+256h`, with both coordinates of `ell` in `[-128,127]`, the first
coordinate of `h` in `[-184,184]`, and the second in `[-106,106]`.
Thus two finite rectangular point tables cover every terminal state.

| Mathematical result | Lean declaration | Hypotheses and status |
| --- | --- | --- |
| Four-corner radix-671 digit coverage | `PrimeJ0SplitTopDigitCover.nearest_digit_bound` | Every integer pair; checked |
| Twelve-step terminal bound | `PrimeJ0SplitTop.twelve_steps_top_bound` | Valid steps, initial `3Q≤n`, digits `3Q≤671²`; checked |
| Coordinate and split bounds | `PrimeJ0SplitTop.top_coordinate_box`, `split_top_box` | Any pair with `3Q≤1668628670`; checked |
| Split scalar reconstruction | `PrimeJ0SplitTopDigitCover.scalar_split_reconstruct` | Every integer scalar under the pinned representative; checked |
| Subgroup congruence | `PrimeJ0SplitTopDigitCover.scalar_split_congruence` | Every integer scalar, pinned subgroup order and scalar map; checked |
| Universal split-table coverage | `PrimeJ0SplitTopDigitCover.scalar_split_box` | Every integer scalar; checked |

[`check.py`](check.py) pins Lean 4.34.1, builds the imported secp256k1
representative modules and both new modules, rejects unverified proof tokens,
and audits every `#print axioms` declaration. The retained
[`lean-build.txt`](lean-build.txt) records source hashes, exact build order,
and foundation axioms; only `propext`, `Classical.choice`, and `Quot.sound`
occur. The Python atlas has its own exhaustive residue and point-replay
checks. The Lean recoder proves the arithmetic format for a four-corner
chooser; the Python atlas's particular tie choices are verified separately.
