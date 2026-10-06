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

Use the accepted Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1459_leaf_lift_screen/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1459_leaf_lift_screen/screen_lift.py --check
```
