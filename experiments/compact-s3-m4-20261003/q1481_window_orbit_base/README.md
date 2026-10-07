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

## Frozen exact-base result

The design was published in commit `989153b6`; source, reference artifacts,
the checked Sage runtime, and the [frozen protocol](protocol.json) were
published in commit `3bebb9a2`, before enumeration. The exact projected
point-set archives store one sorted canonical `x` key per signed-Frobenius
column. Expanding each key by both signs and all `n` Frobenius powers gives
the full subgroup-usable base. In both measured degrees, projection produced
no identity or duplicate orbit.

| Degree and window | Raw `x` orbits | Rational orbits | Actual `B` before folding | Folded `K` | Exact set SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| N53 `d=14` | 8,192 | 4,060 | **430,360** | **4,060** | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| N83 `d=23` | 4,194,304 | 2,096,424 | **348,006,384** | **2,096,424** | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

The [N53 receipt](n53_d14_base.json), [N83 receipt](n83_d23_base.json),
and corresponding packed key archives retain the exact point sets, strata,
source/runtime provenance, exploratory construction wall times, and peak memory.
The [archive audit](archive_audit.json) checks the full packed-key digests and
uses separate curve group operations on 68 N53 and 121 N83 raw masks,
including independently chosen masks from every span. The
[small-field check](window_validation.json) exhaustively confirms the
representative formula on four `(n,d)` cases. Q1481's N53 base has 1.33×
Q1438 W≤4's usable `B`; the N83 base has 0.85× Q1438 W≤6's. This is an
explicit **factor-base change**, so a future solver comparison must say so.

These rows contain no ordinary query, verified relation, natural yield,
cost per useful row, or N131 full-solve work. The N131 window base has not
been enumerated, so its actual `B`, folded `K`, and set digest remain null.

## Reproduce archive checks

```sh
python3 experiments/compact-s3-m4-20261003/q1481_window_orbit_base/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1481_window_orbit_base/validate_window.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1481_window_orbit_base/verify_base.py --check
```

The enumerator refuses to overwrite the archived base and point-set files.
