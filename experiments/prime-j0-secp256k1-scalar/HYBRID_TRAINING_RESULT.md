# Fixed-alphabet hybrid training choice

The pure-ring recoder and scoring rule were frozen in `298615ea`
before the 64 optional-seed masks were scored on the previously
committed 32-case `full-prep-result.json` panel. The source checks
exact reconstruction of every `(a,b)` pair. The full per-mask score
table, training artifact digest, and source hashes are in
`hybrid-training-result.json`.

The selected fixed mask is **31**, allowing width-four seed indices
`{0,1,2,3,4,5,6,7}` and excluding seed `8=1−2τ` from that
width-four digit set. When the canonical width-four digit would use
seed 8, the recoder uses the width-three digit for the same current
ring state. It makes one decision at each nonzero position and does
not search masks at scalar-evaluation time.

| Retrospective 32-case training model, `M+S` excluding inversion | Total |
| --- | ---: |
| Pure width-three, mask 0 | 43,835 |
| Selected fixed hybrid, mask 31 | 42,480 |
| Pure width-four, mask 63 | 42,774 |

The selected mask is 294 modeled units below width-four over 32
training scalars, or 9.19 per scalar. This is **training evidence only**.
The score excludes ring recoding cost, source-level branching, table
lookup, allocation, inversion conversion, and all CPU timing. A
fresh paired holdout with independently checked elliptic-curve
outputs is required before treating the design as a result.
