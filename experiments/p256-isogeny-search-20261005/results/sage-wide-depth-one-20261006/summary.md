# Widened one-hop P-256 isogeny search

## Result

SageMath 10.6 enumerated every rational one-hop isogeny from P-256 for the
ramified or split prime degrees through 47:

```text
3, 5, 11, 13, 17, 23, 29, 37, 41, 43, 47
```

The search retained P-256 plus 20 neighbors. Degrees 3 and 5 contributed one
direction each; every listed split degree contributed two. All explicit paths,
kernel polynomials, rational maps, and transported generators verified. Every
curve had geometric automorphism order 2.

The six neighbors through degree 13 were already present in the prior
depth-three graph. The 14 degree-17 through degree-47 neighbors were all new,
bringing the combined explicit registry to 70 unique curves: 56 in the
small-prime depth-three traversal plus 14 new one-hop curves.

## Timing screen

All 14 new curves were benchmarked in three order-balanced blocks, each with a
P-256 control and per-curve warm-up. The first two blocks used seven one-second
trials per curve. The final P-256-plus-two block used 12 one-second trials, four
complete timing-position rotations.

No candidate had a paired 95% interval excluding `1.0`. The largest estimate
was one degree-47 neighbor:

```text
paired speed = 1.0258x
95% interval = 0.9959x–1.0565x
```

All rho linear-relation checks passed. Because there was no unadjusted screening
hit, no candidate was promoted to a longer holdout.

## Cost and claim boundary

- Reusable candidate discovery took 18.189 seconds, excluding container startup.
- One-hop degree products range from 17 through 47 for the new candidates.
- Explicit formulas needed to map both source points are retained, but per-key
  evaluation remains untimed.
- The host was not CPU-isolated and the benchmark is reference Python.

This run supports only a narrow negative statement: no reproducible reference
rho iteration-rate advantage was detected among the 14 new low-degree one-hop
neighbors. Together with prior runs, 37 distinct neighbors have now been timed
and 70 unique curves carry explicit paths. This remains far from an exhaustive
class-group search and is not an end-to-end per-key attack comparison.
