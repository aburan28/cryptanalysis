# Proof map and mathematical argument

## Four-corner covering theorem

For an Eisenstein pair `z=(a,b)`, put `u=a+b`, `v=-b`. Its norm becomes

`Q(a,b)=a²+3ab+3b²=u²−uv+v²`.

At radix `R=943`, take the Euclidean floors `fᵤ=⌊u/R⌋` and
`fᵥ=⌊v/R⌋`. The chooser examines the four corners
`(m,n)∈{fᵤ,fᵤ+1}×{fᵥ,fᵥ+1}`. Its residual is
`(x,y)=(u−mR,v−nR)`, digit `d=(x+y,−y)`, and quotient
`q=(m+n,−n)`. Direct expansion gives the exact step equation
`z=d+Rq`.

Write `r=u mod R`, `s=v mod R`, so `0≤r,s<R`. The four residuals are
`(r,s)`, `(r,s−R)`, `(r−R,s)`, and `(r−R,s−R)`. Define the hexagonal
cell by

`|2x−y|≤R`, `|2y−x|≤R`, `|x+y|≤R`.

Every such residual obeys `3Q(x+y,−y)≤R²`. Indeed, for
`p=2x−y`, `q=2y−x`, we have
`3Q(x+y,−y)=p²+pq+q²` and `p+q=x+y`. When `p,q` have the same
sign, the expression is at most `(p+q)²`. When their signs differ, it
is at most `p²` or `q²`, according to the sign of `p+q`. Each square
is at most `R²` under the cell inequalities.

The four cells cover the residue square. By symmetry suppose `r≥s`.
If `2r−s≤R` and `r+s≤R`, use corner `(0,0)`. Otherwise, if
`2s≤r`, use `(R,0)`: the failed origin condition and `r−2s≥0`
give `2r−s≥R`. In the remaining case use `(R,R)`: the failed
origin condition and `r−2s<0` give `r+s≥R`. Each case satisfies the
six linear hex-cell inequalities. Swapping `r,s` handles the other
half of the square. The chooser selects the lexicographically least
`(Q(d),d₁,d₂)` among the four digits, so its digit norm is no greater
than that of the covered corner.

The Lean definition `nearestStep` follows the Python and Rust loop
order and tuple tie-break. `nearest_step_equation` proves its quotient
equation for every integer input. `nearest_digit_bound` proves its
unconditional digit bound. Both results quantify over all integer
pairs, rather than only the `943²` residue inputs of the earlier
exhaustive screen.

## Thirteen-window composition

`recode n z` repeatedly applies `nearestStep`, collecting digits from
least significant to most significant. Lean proves its length, every
digit bound, and the exact `Recodes` relation used by the prior
termination theorem. Hence
`nearest_thirteen_terminate` proves `(recode 13 z).2=(0,0)` whenever
`3Q(z)≤n`, with
`n=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141`.
It invokes the checked integer inequality and positive-definite norm
argument in `../prime-j0-radix943-termination-20261012/Termination.lean`.

## Initial representative and scalar congruence

The implementation's exact lattice basis is `V=(-U₂,C)` and `W=U−2V`,
where `U=(193508920647619669885755136084601127231,
238911465918039986966665730306072050094)` and
`C=303414439467246543595250775667605759171`. Lean checks
`det(W,V)=n` and `Q(W)=Q(V)=Q(W+V)=n` by kernel reduction. The norm
identities imply the Gram equation

`Q(xW+yV)=n(x²−xy+y²)`.

For any integer scalar `k`, the exact basis-coordinate numerators of
`(k,0)` are `t=kV₂` and `w=−kW₂`. The chooser examines the four corners
around `(⌊t/n⌋,⌊w/n⌋)`, using the same lexicographic key as Python:
`(Q(z), max(|z₁|,|z₂|), z₁, z₂)`. For corner `(m,j)` and resulting
representative `z=(k,0)−mW−jV`, the determinant identity gives

`n z=(t−mn)W+(w−jn)V`.

The two numerators have remainders in `[0,n)`. Applying the same
four-corner hexagonal cover at `R=n` gives one corner with
`3(x²−xy+y²)≤n²`. The Gram equation and `Q(nz)=n²Q(z)` then give
`3Q(z)≤n`; the chosen minimum obeys this bound too. Lean proves it as
`nearest_representative_bound k` for every integer `k`. Thus
`scalar_recode_terminates k` has no covering-bound premise.

With the exact endomorphism eigenvalue
`λ=0xac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0`,
Lean also checks `W₁+λW₂=n·kernelW` and `V₁+λV₂=n·kernelV` for the
integer cofactors in the module. Subtracting basis multiples preserves
`a+λb≡k (mod n)`. `scalar_recode_reconstruct` equates the thirteen
digit sum with the chosen representative; `scalar_recode_congruence`
therefore proves that digit sum represents the original scalar modulo
the secp256k1 subgroup order.

| Result | Lean declaration | Exact hypotheses | Status |
| --- | --- | --- | --- |
| Hex-cell norm inequality | `hex_energy`, `hex_digit_bound` | Six cell inequalities over integer `x,y,R` | Checked |
| Four-corner residue-square cover | `upper_cover`, `four_corner_cover` | `0≤r,s≤R`; applies in particular to `r,s∈[0,942]` | Checked |
| One concrete chooser step | `corner_equation`, `nearest_step_equation`, `nearest_digit_bound` | Any integer pair, `R=943`, Euclidean floors and four-corner lexicographic minimum | Checked |
| Recoder length, digit bounds, and exact quotient chain | `recode_length`, `recode_digit_bounds`, `recode_steps` | Any integer pair and natural window count | Checked |
| Zero terminal state after 13 steps | `nearest_thirteen_terminate` | `3Q(z)≤n` for the exact secp256k1 subgroup order above | Checked |
| Lattice determinant, Gram form, and endomorphism kernel arithmetic | `basis_determinant`, `basis_norms`, `basis_kernel` | Exact `U,V,W,n,λ` integers in the module | Checked by kernel reduction |
| Initial scalar-to-lattice representative bound | `nearest_representative_bound` | Any integer scalar; exact `W,V` basis and four-corner chooser | Checked |
| Full scalar recoding termination and congruence | `scalar_recode_terminates`, `scalar_recode_reconstruct`, `scalar_recode_congruence` | Any integer scalar, 13 windows, exact `n` and `λ` | Checked |
| Rust word, orbit-atlas, and curve-operation refinement | Native and independent point replays | Exact format-174 implementation and secp256k1 point formulas | Computationally checked; Lean refinement open |

The pinned build compiles the prior termination module and this module
with Lean 4.34.1. The `#print axioms` output for the public results
contains only Lean's standard `propext`, `Classical.choice`, and
`Quot.sound` foundations; the integer basis certificates and
`recode_length` have no axioms. The theorem
source has no `sorry`, `admit`, native-evaluation bridge, or custom
research axiom. `lean4checker --fresh` is unavailable on this host.

The 42 saved digit fixtures compare the executable Lean chooser with
the independently executed Python chooser and check each quotient
equation. Twelve scalar fixtures compare the complete Lean and Python
representatives and thirteen-digit lists. These fixtures test
correspondence between definitions; the all-input bounds, termination,
and congruence results follow from the Lean proofs above.
