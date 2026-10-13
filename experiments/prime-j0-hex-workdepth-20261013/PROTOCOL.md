# Count-based work/depth scheduling for the hex terminal

The secp256k1 hex-terminal recoder selects at most sixteen affine points.
Their unit gauges are in `{0,1,2}`. This experiment uses only the three
gauge counts to choose an addition tree. It keeps the recoder, point table,
input scalar, selected points, and native group formulas from the preceding
experiment fixed.

`optimize.py` memoizes count triples. For every nonempty split of a triple,
it combines retained child schedules under each child's output gauge. The
model charges six field products for an affine/affine join, ten for an
affine/projective join, fourteen for a projective/projective join, and one
for each gauge rotation. Within each output gauge, it retains the candidate
with least modeled products plus rotations, breaking ties by dependency
depth and rotations. A final gauge-zero rotation is charged when needed.
This is a finite operation-model search; its exact recurrence and all input
patterns are executable in `optimize.py`. The existing abstract Lean theorem
`PrimeJ0GaugeTree.reordered_tree_correct` supplies the conditional group-sum
identity for any reordered tree. This experiment has no Lean proof that the
DP's chosen schedule minimizes the cost across every possible native
execution path; it reports model values and independent native point replay.

`make_plans.py` converts the chosen trees into the same 48-byte plan record
format as the preceding experiment. It independently replays all 969
gauge-count patterns, including the empty selection. The table stays
46,512 bytes. `native_overlay_workdepth.py` builds the unchanged native
gauge-tree evaluator with these new plan bytes in a disposable checkout.
`check.py` verifies every native point against the independent fixture and
every addition and rotation count against the count-based model.

The design panel and the preceding 512-scalar holdout were already known
when this search was built. They are screening and calibration inputs. The
source, plan table, native binary, and calibration receipts must be committed
before a new disjoint scalar panel is generated. A CPU wall-time comparison
requires a qualifying isolation receipt and complete-operation boundaries.

Reproduce the model and table with:

```sh
python3 experiments/prime-j0-hex-workdepth-20261013/optimize.py
python3 experiments/prime-j0-hex-workdepth-20261013/make_plans.py
python3 experiments/prime-j0-hex-workdepth-20261013/check.py \
  experiments/prime-j0-hex-tree-20261013/holdout.json \
  experiments/prime-j0-hex-workdepth-20261013/calibration-native.jsonl \
  experiments/prime-j0-hex-workdepth-20261013/calibration-receipt.json
```
