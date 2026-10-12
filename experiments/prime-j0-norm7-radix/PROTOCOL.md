# Norm-seven Eisenstein-radix feasibility screen

Freeze this protocol and `screen.py` before its checked Sage run. Work
on secp256k1 with `ω(x,y)=(βx,y)`, `τ=1−ω`, and the alternative radix
`ρ=2−ω=1+τ`, whose Eisenstein norm is seven. In the `(1,τ)` basis,
`ρ(a,b)=(a−3b,a+4b)`. Build a width-two digit table by selecting the
least Eisenstein-norm representative in every residue class modulo
`ρ²` that is not divisible by `ρ`, with deterministic tie-breaking.
Recode the 64 short scalar representatives in the already frozen native
fixture; verify exact reconstruction, descent, and finite length.

Independently verify the direct degree-seven projective map on every
fixture base, using affine and two nontrivial Jacobian scales, against
Sage's group expression `2P−ω(P)`. The map is derived from the
degree-seven kernel with `x³=c`, where
`c=−4b/(1+3β)` for curve coefficient `b=7`:

```
Z6 = Z^6; U = X^3; C = c Z6; B = b Z6; D = U-C
N = D^2 + 18 C D + 12(C+B)(U+2C)
N_U = 2D + 30C + 12B
M = (N+3U N_U)D - 6U N
(X',Y',Z') = (X N, Y M, (2−β) Z D)
```

This literal projective expression costs `13M+4S` per radix step if
constant field multiplications count as `M`, or `12M+4S` if `b=7`
multiplication is charged only as additions. Compare **only the radix
steps** (zero digit-add and zero table-preparation cost, an optimistic
bound) with the frozen cached-projective width-four `M+S` total on the
same 64 short representatives. Do not promote a CPU or novelty claim
from source counts. If the lower bound already loses, stop this
particular formula before implementing a native scalar pipeline.

Save `sage --runtime-info` before execution. Retain the frozen fixture,
source, runtime, per-case recode and map checks, exact costs, and any
failures. This screen concerns this direct norm-seven formula; it
cannot rule out a different or more efficient map for the same radix.
