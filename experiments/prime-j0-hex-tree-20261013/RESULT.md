# Gauge-aware addition tree for the hex terminal

The frozen native evaluator reproduces all 512 independently generated
secp256k1 points in a fresh scalar panel. It retains the hex-terminal
recoder and 7,680 group additions, while changing the order of those
additions. On this panel, the operation model lowers aggregate product
dependency depth from 77,824 to 25,299 (67.49%) and modeled products plus
rotations from 77,824 to 76,678 (1.47%). The native evaluator records 1,926
gauge rotations, matching the frozen model; the serial reference records
1,024. The plan table adds 46,512 retained bytes, for 11,552,448 total.

`holdout.json` was generated after native source commit `b9b7e3cdb` from a
seed derived from that commit. Its 512 scalar inputs are disjoint from the
design and earlier holdout panels. `holdout-receipt.json` checks every point
against the independent point fixture and checks additions and rotations
against the frozen model, case by case. The serial and tree native binaries
both replay the same fixture; their source and binary hashes are in the two
native receipts. `lean-check.log` records a fresh build and axiom audit of
the abstract gauge-tree group-sum theorem with Lean 4.34.1. The theorem
assumes the concrete automorphism and a leaf permutation; native fixture
replay checks this implementation's point result.

Seven boundary scalars also replay in both native evaluators: zero, one,
two, `r−1`, `r`, `r+1`, and `2^256−1`. `edge-receipt.json` checks their
independent points. An initial edge fixture omitted the base coordinates
required by the CLI; its panic output and malformed fixture are retained
and classified as an input-schema error. The corrected fixture passed 7/7.

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
additions and 1,021 rotations exactly. The native gauge-tree evaluator now
replays all 512 points of that same existing fixture and records 7,679
additions and 1,909 rotations, matching the tree model. It also replays all
512 points of the earlier hex-terminal holdout. These are calibration
controls available before the tree source was frozen. The depth and product
totals are operation-model results, with recoding,
table lookup, exceptional paths, plan lookup, memory traffic, and affine
recovery outside the model. No CPU wall-time result is inferred.

Complete-operation wall time remains to be measured on a qualifying isolated
host. The model omits recoding, table lookup, exceptional paths, plan lookup,
memory traffic, and affine recovery, so its depth and work totals are not CPU
speedup estimates. The existing RunPod CPU container fails the repository's
isolation preflight; its timing is exploratory.
