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
and this calibration panel were known before the source freeze.

The disjoint 512-scalar holdout was generated from source commit
`3bb8bace32d5ba549888e7118d201ae5c2aecfd8` and excludes the design
panel and all twelve prior panels listed in `holdout.py`. Its fixture SHA-256
is `cbc3c614e8bdf251bf30e515c238e48d21d4b7b7b6004e90fbf5b350dde17ae6`.
The same native evaluator verified every independently generated point;
the panel has 7,679 additions, 1,021 rotations, and 11,552,448 retained
bytes. On these unseen inputs, 252 cases have shorter modeled DAG chains.
Aggregate depth is 7,371 versus 7,623 for the previous plan, a 3.31%
reduction, with both plans at 75,763 modeled join calls. `holdout-check.json`
binds the fixture, rows, checker, and plan table.

An instrumented build counted actual `u256_mul_solinas_with` invocations
across the same holdout. Its join interval made **75,763 calls**, exactly
matching the plan model for every case. Affine recovery made 2,048 more;
the total was 77,811. `opcount-receipt.json` binds the instrumented binary,
overlay, raw rows, and per-case checker. The counter covers this
single-threaded fixture CLI, including squares through the Solinas kernel.
The formula-DAG score remains a source-derived operation-dependency
diagnostic. A calibrated isolated-host run is needed to measure
complete-operation wall time.
