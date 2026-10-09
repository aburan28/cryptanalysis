# Deferred normalization across a tau point step

One secp256k1 tau step can evaluate its five field products by Eisenstein
Montgomery reduction without balancing their intermediate residues. Integer
linear combinations are carried in the same pair representation, and only
the three final Jacobian coordinates are balanced. A deterministic screen
verified the resulting tau point against independent `P - omega(P)` group
addition on 34 points with random projective scales, plus 10,003 field
triples. This identifies a complete point formula that can amortize the
normalization cost of the two-coordinate field representation.

## Width bound for one step

Write `R=2^128`, `p=R^2-(2^32+977)`, and use the complex absolute value
`|a+b*omega|=sqrt(a^2-a*b+b^2)`. A balanced field element has norm at most
`p/3`, so its magnitude is strictly below `3R/5`. For a raw Montgomery
product of operands bounded by `A*R` and `B*R`, the cancellation pair has
norm below `R^2`; the output magnitude is therefore below `(A*B+1)*R`.
These bounds do not depend on the sampled inputs.

For balanced Jacobian input `(X,Y,Z)`, apply the tau formula from the native
scalar path. The following upper bounds are in units of `R`:

| Intermediate | Construction | Magnitude bound |
| --- | --- | ---: |
| `X2`, `Y2` | raw square | `34/25` |
| `X3` | raw `X2*X` | `227/125` |
| `RX` | `4*Y2 - 3*X3` | `1361/125` |
| `inner` | `3*X3 - 2*RX` | `3403/125` |
| `RY` | raw `Y*inner` | `10834/625` |
| `(1-omega)*X` | linear coefficient map | `21/20` |
| `RZ` | raw `((1-omega)*X)*Z` | `163/100` |

The coefficient inequality `|a|,|b| <= 2|a+b*omega|/sqrt(3) < 6|.|/5`
puts **every intermediate coefficient below `33R` (134 bits)** and each
final tau coefficient below `22R` (133 bits). This permits a fixed-size
three-limb signed coefficient through one tau step, followed by balancing
before the next point step. The reference screen observed maxima of 133
bits for an intermediate and 132 bits for a final coordinate.

## Division-free quotient for final balancing

For an unbalanced final coordinate `u`, set `t=u*conjugate(pi)`.
The bound above gives each `|t_i| < 22R^2`. Let `C=R^2-p`; since
`22C < p`, the real quotients `t_i/p` and `t_i/R^2` differ by less than one.
Start with the arithmetic shift `k_i=floor(t_i/R^2)`. Comparing
`t_i-k_i*p` with `0` and `p` adjusts `k_i` by at most one to obtain the
exact `floor(t_i/p)`. Check the lattice points with coordinates
`k_i` or `k_i+1` in each coordinate, and choose the minimum norm with a fixed
tie rule. These **four corners suffice**: a nearest Eisenstein lattice point
is at distance at most `1/sqrt(3)` in the normalized lattice, while the
coefficient inequality bounds each coordinate difference by `2/3`. An
integer within `2/3` of a coordinate between `k_i` and `k_i+1` must be one
of those two integers.
The screen's Python assertion against direct division is a verification
oracle; a native implementation needs only shifts, fixed-width additions,
small constant products, and comparisons.

## Replay evidence and next native step

Run `python3 experiments/prime-j0-secp256k1-native/lazy_tau_screen.py`.
With seed `20261009`, the screen checked 10,003 field triples and 34 curve
points, including the generator and its double. Every final balanced pair
matched the exact reference, every decoded tau coordinate matched the
canonical formula, and each affine point matched `P - omega(P)`. It also
checked 246 quotient values near multiples of `p`; 119 required the
one-step correction. The random tau panel required none. The source SHA-256
for this run was
`6c0a4f3423e0b69ba3399f1712da6bf4f6bc766030565783d0cfa81298d65c43`.

The next implementation step is to add raw reduction and this final
normalizer to the fixed-width Rust kernel, then replay complete tau and rho
point operations and scalar multiplication. The current screen records
correctness and width bounds; it contains no CPU timing ratio.
