# Gauge-tree formula-DAG plan

The bounded count-triple search selected 225 changed records among 969
patterns while preserving the 46,512-byte table and the prior plan's
modeled Solinas-call work for every pattern. The selected records never
increase the formula-derived coordinate DAG depth. On the previously known
512-scalar calibration panel, 232 cases use a shorter DAG chain; aggregate
depth falls from 7,587 to 7,355, a 3.06% reduction in this model. Both
plans require 75,775 modeled join calls. The native evaluator verified all
512 independently generated secp256k1 points, 7,680 group additions, 1,023
gauge rotations, and 11,552,448 retained table bytes.

`plans.json`, `calibration-check.json`, and `native-receipt.json` bind the
plan generator, table, fixture, native rows, and binary. The design panel
and this calibration panel were known before the source freeze; a disjoint
post-freeze holdout is the next correctness check. The formula-DAG score is
an operation-dependency diagnostic. A calibrated isolated-host run is needed
to measure complete-operation wall time.
