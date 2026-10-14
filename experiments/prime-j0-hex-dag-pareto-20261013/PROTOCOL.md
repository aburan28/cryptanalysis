# Formula-DAG-aware gauge-tree scheduling

The secp256k1 hex-terminal evaluator uses at most sixteen selected affine
points in three unit gauges. This experiment changes only the 48-byte plan
record selected by the three gauge counts. The native recoder, table, group
formulas, and point fixtures stay fixed.

`pareto.py` explores count-triple splits and both child output gauges. It
propagates work and the x, y, zz, and zzz multiplication-dependency depths
from `dag_depth.py`, which mirrors the ordinary native addition formulas.
Within each output gauge it removes dominated states and retains at most
twelve according to `(work, longest depth, sum of coordinate depths)`.
This beam is a bounded heuristic; it is not an exhaustive Pareto frontier.
For each count triple, `choose` accepts a tree only if its work is at most
the frozen low-work tree's work and its longest formula-DAG chain is
strictly shorter. Otherwise the frozen record is copied byte-for-byte.

`make_plans.py` independently encodes and replays all 969 count patterns.
It verifies equal work and nonincreasing formula-DAG depth for every
record. `native_overlay_pareto.py` swaps the resulting 46,512-byte table
into the unchanged evaluator in a disposable build directory. `check.py`
reconstructs gauge counts from each scalar, verifies every native point
against independently generated coordinates, checks addition and rotation
counts, and recomputes the formula-DAG score from both plan tables.

The 4,096-scalar design panel and preceding 512-scalar holdout were already
known while choosing the plan. Their results are calibration only. Source,
plan table, native build, and calibration receipts are committed before a
new disjoint 512-scalar holdout is generated from the source commit hash.
The holdout generator excludes those panels and every earlier listed panel.

The score counts the longest chain of source-derived Solinas multiplication
or square calls inside the join formulas, assigning each call unit depth.
It excludes recoding, table traffic, affine inversion, instruction scheduling,
and memory effects. The native operation counter in the preceding experiment
validated the frozen work model; this experiment preserves that work for
every count pattern. Controlled wall-time comparison requires a qualifying
CPU isolation receipt. The abstract group-sum identity is checked by
`PrimeJ0GaugeTree.reordered_tree_correct`; the Rust-to-Python formula-DAG
bridge remains an explicit proof obligation, so the DAG score is a model
diagnostic rather than a formal theorem about native execution.

Reproduce the frozen table and calibration checks:

```sh
python3 experiments/prime-j0-hex-dag-pareto-20261013/make_plans.py
python3 experiments/prime-j0-hex-dag-pareto-20261013/check.py \
  experiments/prime-j0-hex-workdepth-20261013/holdout.json \
  experiments/prime-j0-hex-dag-pareto-20261013/calibration-native.jsonl
python3 experiments/prime-j0-hex-dag-pareto-20261013/holdout.py --check
python3 experiments/prime-j0-hex-dag-pareto-20261013/check.py \
  experiments/prime-j0-hex-dag-pareto-20261013/holdout.json \
  experiments/prime-j0-hex-dag-pareto-20261013/holdout-native.jsonl
python3 experiments/prime-j0-hex-dag-pareto-20261013/check_opcount.py
```
