# Root-first Eisenstein seed graph

Root-first construction lowers the source-level Q-seed `add_projective` count
from 62 to **55** for the frozen one-restart stream and from 667 to **660** for
the frozen 128-restart stream. It uses the same scalar recoding, requested
seeds, Q input, and native evaluator as the [joint graph
experiment](../prime-j0-eisenstein-residue-20261015/JOINT_SEED_GRAPH.md).

The [planner](root_first_plan.py) treats each requested Eisenstein coefficient
pair as a graph vertex. A directed edge records a coefficient identity

`target = unit(parent) + unit(2^bit * basis)`

where `basis` is Q or the order-three image of Q and `unit` is one of three
rotations with either sign. It finds connected components of these available
edges, chooses a low binary-weight direct root in each component, and walks
outward while recording explicit parent and step witnesses. The native plan
loader checks each coefficient identity and topological dependency before it
constructs Q points. This changes the graph order and root selection; it does
not change the scalar digits or target-independent generator table.

| Restarts | Requested seeds | Direct roots | Earlier additions | Root-first additions |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 21 | 8 | 62 | 55 |
| 128 | 659 | 1 | 667 | 660 |

The count includes calls in direct-root construction, including calls whose
left operand is the identity, plus one call per graph edge. It excludes the
shared binary-power preparation, normalization, graph search, and evaluation.
The [one-restart](root-first-1-receipt.json) and
[128-restart](root-first-128-receipt.json) receipts pin the input and output
plan hashes. The plans are [one restart](root-first-plan-1.json) and
[128 restarts](root-first-plan-128.json).

The [local replay](root-first-local-replay.json) invokes both native planned
evaluators on the original Q and four independently constructed Q values. It
checks every frozen point in the one- and 128-restart streams plus the
alternate one-restart points. These local invocations provide correctness and
operation-count evidence; wall-time comparison remains in the Tier 1 paired
panel. The [existing Lean graph proof](../prime-j0-eisenstein-residue-20261015/JointSeedGraph.lean)
covers the unit-edge coefficient-to-point implication used by every emitted
edge, under its stated additive and unit-action hypotheses. The native replay
checks the concrete secp256k1 implementation.

To regenerate the plans from the frozen source artifacts:

```sh
python3 root_first_plan.py \
  --source ../prime-j0-eisenstein-residue-20261015/rho-joint-graph-plan-1.json \
  --output root-first-plan-1.json --receipt root-first-1-receipt.json
python3 root_first_plan.py \
  --source ../prime-j0-eisenstein-residue-20261015/rho-joint-graph-plan-128.json \
  --output root-first-plan-128.json --receipt root-first-128-receipt.json
```

The plans are compatible with the existing
`--pilot-rho-restart-joint-graph-planned` and
`--pilot-rho-restart-joint-fused-graph-planned` commands. A future Tier 1
panel should add the root-first plans as distinct frozen arms, with a same-Q,
same-scalar paired comparison and the usual calibration and noise gates.
