# Published triple-and-add formula: source-count feasibility screen

The width-four evaluator already uses `τ² = −3ω`, where `τ=1−ω`
and `ω²+ω+1=0`. This suggested replacing a paired τ stride followed
by a digit addition with a single `3P+Q` formula, after applying the
cheap unit `−ω` to the accumulator.

[Longa's composite-operation thesis, §3.2.2](https://eprint.iacr.org/2008/100.pdf)
gives a Jacobian/affine `3P+Q` construction at `18M+7S`, or **25
`M+S` units** in this repository's unweighted source-count convention.
The frozen evaluator's paired τ stride costs **10** units. Its next
addition costs **11** for a mixed affine seed and **14** for a cached
projective seed. Thus the existing pair-plus-add path costs **21** or
**24** units. The published affine-input triple-and-add formula is
already 4 or 1 units more expensive, respectively; the latter
comparison even grants the formula an affine `Q` that the cached
projective path does not provide.

This rejects that **literal published formula** as a substitute in
the current source-count model. It does not bound a new secp256k1-
specific fused formula. To beat the current path by at least one unit,
such a formula must cost at most **20** with an affine base digit or
**23** with a cached projective digit, including any coordinate
conversion, and must handle identity/equal-point cases. No native
implementation, isolated CPU timing, or academic novelty claim follows
from this algebraic screen.
