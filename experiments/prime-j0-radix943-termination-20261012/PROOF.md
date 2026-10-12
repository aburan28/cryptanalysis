# Proof map and readable argument

Write an Eisenstein pair as `z=(a,b)` and define
`Q(z)=a²+3ab+3b²`. The identity
`4Q(z)=(2a+3b)²+3b²` proves nonnegativity and that `Q(z)=0` only for
`z=(0,0)`. For pairs `x=(a,b)` and `y=(c,d)`, let
`B₂(x,y)=2ac+3ad+3bc+6bd`. Expanding gives

`4Q(x)Q(y) − B₂(x,y)² = 3(ad−bc)² ≥ 0`.

Consequently, if `3Q(x)≤K²`, `3Q(y)≤R²`, and `K,R≥0`, then both
`3Q(x+y)` and `3Q(x−y)` are at most `(K+R)²`. Lean proves this by
bounding the mixed term with the square identity, using multiplication
monotonicity and an explicit square comparison. The same norm is
homogeneous: `Q(kz)=k²Q(z)`.

For the digit list, define `decode []=0` and
`decode (d::tail)=d+943 decode tail`. Define the radius recurrence
`S₀=0`, `Sᵢ₊₁=943+943Sᵢ`. Under `3Q(dᵢ)≤943²`, induction with the
triangle bound gives `3Q(decode digits)≤S₁₃²` for thirteen digits.
The `Recodes` relation records every exact quotient equation and proves
`start=decode digits+943¹³ terminal` by induction. Applying the norm
bound to `start−decode digits` yields

`3·943²⁶ Q(terminal) ≤ (2¹²⁸+S₁₃)²`.

Lean checks the strict numeric inequality on the right:

| Quantity | Exact integer |
| --- | ---: |
| `S₁₃` | 466780597438322804778374027146450644943 |
| `(2¹²⁸+S₁₃)²` | 651350628440358224124238101989970066222256118655262501573337863827367383247201 |
| `3·943²⁶` | 652266788196859845275623226369043785643589744678153169412500491536255330555747 |

It follows that `Q(terminal)<1`; as a nonnegative integer this norm is
zero, hence the terminal pair is zero.

| Result | Lean declaration | Exact hypotheses | Status |
| --- | --- | --- | --- |
| Norm positive definiteness and Cauchy identity | `norm_four_square`, `norm_nonneg`, `norm_zero`, `cross_square`, `cross_bound` | Integer pairs with `Q(a,b)=a²+3ab+3b²` | Checked |
| Norm radius propagation | `norm_add_bound`, `norm_sub_bound`, `norm_scale_bound` | The stated squared norm bounds and nonnegative radii | Checked |
| Digit-list and quotient reconstruction | `norm_decode_bound`, `recodes_reconstruct` | Every listed digit obeys `3Q(digit)≤943²`; every `Recodes` step has its exact integer equation | Checked |
| Secp256k1 initial and thirteen-window arithmetic certificates | `initial_radius_certificate`, `thirteen_window_certificate` | Exact subgroup order, `R=943`, thirteen windows | Checked by kernel reduction |
| Zero terminal pair | `thirteen_steps_terminate` | Thirteen steps, `3Q(start)≤n`, each digit bound, and `Recodes start digits terminal` | Checked |
| Concrete chooser satisfies initial and digit bounds | Prior lattice argument and `../prime-j0-secp256k1-native/radix943-screen-result.json` | Four-corner representative and digit algorithms on secp256k1 | Written proof and exhaustive residue check; Lean refinement open |
| Rust word quotient and table point link | Native and independent point replays in `../prime-j0-radix943-pareto-20261012` | Exact implementation and curve formulas | Computationally checked; Lean refinement open |

The `#print axioms` output in `lean-build.txt` reports only `propext`,
`Classical.choice`, and `Quot.sound` for the substantive theorems; the
two fixed-number certificates report no axioms. `lean4checker --fresh` is
unavailable on this host. The current full-format formalization remains
partial until the nearest-chooser bounds and Rust refinement are proved in
Lean. No conclusion of the termination theorem is built into its premises.
