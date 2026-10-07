# Q1481: Frobenius orbit union of linear windows

The [pre-registered design](design_protocol.json) tests a different exact
factor-base policy on the same Koblitz curves used by Q1438. A raw normal-basis
`x` is eligible when all its one bits fit inside **some** cyclic window of
length `d`. This union is Frobenius-stable because squaring rotates the normal
basis coordinates. Once the window position is fixed, its `d` coordinates are
linear free variables. This is a proposed route to a more structured compact
four-summand system; no solver improvement is claimed by the base geometry.

For `2d<n`, every eligible nonzero `x` orbit has one representative immediately
after its unique zero gap of length at least `n-d`. If the representative's
highest one bit is at `t`, there are `2^(t-1)` interior patterns for `t>0`
and one pattern for `t=0`. Hence the **raw x-orbit count** is exactly
`2^(d-1)`. Rationality, cofactor projection, distinct subgroup points, and
folded columns still require exact enumeration; that raw count is never an
`fb<B>` count.

| Degree | Curve ID | Window `d` | Raw x orbits | Existing comparison base | Existing actual `B` / folded `K` |
| ---: | --- | ---: | ---: | --- | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 14 | 8,192 | Q1438 W≤4 | 324,042 / 3,057 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 23 | 4,194,304 | Q1438 W≤6 | 408,131,750 / 2,458,625 |
| 131 | `EC1N131Ckb1h6816f880945e` | 27 | 67,108,864 | Q1413 W≤6 | 6,559,634,788 / 25,036,774 |

Q1481 keeps `candidate_id: null`, `run_id: null`, and `isogeny: "none"`.
The N131 row is a design, with actual `B`, folded `K`, set digest, and complete
`2^x` all unknown. The first measurement is exact N53/N83 base construction
and independent group-law checks. A follow-on point-decomposition stage must
freeze its source, formula, target workload, and resource cap separately and
receive a `PS1...fb<B>...` ID using the *measured* base size.
