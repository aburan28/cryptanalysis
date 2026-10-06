# Q1459: exact curve-lift filtering before the joint pair cap

Q1458 makes the bounded joint `S3` join cheaper but still observes mostly
over-cap partial pair domains. Q1459 tests whether removing impossible leaf
x values **before** forming pair products admits more of the archived
partial states. It is an exact feasibility screen, not a new decomposition
solver or a successful-solve timing.

For the declared binary curve `y² + xy = x³ + 1`, a nonzero x coordinate
lifts to a curve point exactly when `Tr(x + x⁻¹) = 0`. Indeed, with
`z = y/x`, the curve equation is `z² + z = x + x⁻²`, and the two terms
`x⁻²` and `x⁻¹` have the same trace. The screen enumerates one sparse
leaf domain only if it has at most 4,096 possible nonzero x values,
applies this exact condition to each, then multiplies the four surviving
leaf counts into two pair-domain counts. It skips larger leaf domains,
retaining their unknown status. A liftable x is necessary for every valid
factor-base point, so this filtering cannot discard a group relation.

The [frozen protocol](protocol.json) pins Q1456's 15-second N53/N83
partial-state archives and Q1458's exact curve, base, target, and workload
records. It retains actual usable base counts (`B=324,042` at N53 W≤4;
`B=408,131,750` at N83 W≤6), folded columns (`K=3,057` and
`K=2,458,625`), and enumerated-set digests. This is proposal `Q1459`,
`candidate_id: null`, `run_id: null`, `isogeny: "none"`, with stage code
`PDP4hybrid`. The checked Sage runtime receipt was captured before the
screen.

The decisive diagnostic is the number of **new exact admissions** under
the unchanged 4,096 pair cap. If the screen admits additional states,
the next native solver can combine leaf-filtered domains with Q1458's
batched root join and test the same ordinary N53/N83 public targets.
Admission alone does not predict a verified relation, natural yield,
rank, or a complete N131 `2^x`.

## Frozen screen outcome

The [result](result.json) preserves every archived state, raw and
lift-filtered leaf count, pair count, cap decision, and skipped state. The
[independent audit](verification.json) re-enumerates all screened leaf
domains and checks every distinct x with Q1422's separately built native
field and curve-lift implementation: 1,327 distinct x at N53 and 3,161
at N83. It independently reproduces every filtered count and admission.

| Input | Unique partial states | States with every leaf ≤4,096 options | Raw pair-cap admissions | After exact lift filter | New admissions |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 known-satisfiable unpinned slice | 21 | 13 | 6 | 6 | 0 |
| N53 full ordinary target | 21 | 13 | 6 | 6 | 0 |
| N83 full ordinary target | 23 | 7 | 1 | 2 | 1 |

The one new N83 state has 79 raw x options in each leaf, so both pair
products are `79² = 6,241`. Exactly 39 x values per leaf lift to the
curve, reducing each pair product to `39² = 1,521`, below the unchanged
4,096 cap. The 15-second Q1456 prefixes are diagnostic snapshots; the
same state need not be reached on a changed solver path. This screen
does not run the joint solver or return a relation. It establishes that
single-leaf lift filtering alone provides only one extra admission in
these frozen prefixes, so the main solver goal still requires a stronger
target-coupled large-domain condition or a better search policy.

Use the accepted Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1459_leaf_lift_screen/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1459_leaf_lift_screen/screen_lift.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1459_leaf_lift_screen/verify_archive.py --check
```
