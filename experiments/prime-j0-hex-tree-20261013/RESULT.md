# Gauge-aware tree design screen for the hex terminal

The sixteen-selection hex-terminal format admits a 46,512-byte cached
gauge-plan table. On the frozen 4,096-scalar design fixture, its tree
schedule lowers modeled product dependency depth from 622,562 to 202,235
across the panel, a 67.51% reduction. Modeled products plus rotations fall
from 622,562 to 613,140, a 1.51% reduction. The recoder selects the same
65,534 points and requires the same 61,438 group additions under either
schedule. The tree uses 15,144 modeled rotations versus 8,182 for the
serial gauge grouping.

The screen observed 106 distinct gauge-count plans on the design fixture.
`make_plans.py` generated and independently replayed all 969 possible plan
records for zero through sixteen selected points. Its maximum recorded
product depth is 50. `plans.json` pins the table hash and source revisions.

The serial model reproduced the existing native 512-scalar panel's 7,679
additions and 1,021 rotations exactly. That panel is a calibration control;
it was available before this tree schedule. The new tree has not yet been
implemented in the native evaluator or replayed on an unseen scalar panel.
The depth and product totals are operation-model results, with recoding,
table lookup, exceptional paths, plan lookup, memory traffic, and affine
recovery outside the model. No CPU wall-time result is inferred.

The next gate is a native implementation using the frozen plan table,
followed by independent point replay on a newly generated disjoint panel
and matched complete-operation timing on a qualifying isolated host.
