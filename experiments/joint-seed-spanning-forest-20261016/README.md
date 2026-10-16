# Root-first Eisenstein seed graph

Two auxiliary coefficient vertices lower the source-level Q-seed
`add_projective` count from 62 to **25** for the frozen one-restart stream.
Root-first ordering lowers the 128-restart count from 667 to **660**. All use the same scalar
recoding, requested seeds, Q input, and native evaluator as the [joint graph
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

The [two-parent planner](two_parent_plan.py) also searches identities of the
form `target = unit(left) + unit(right)`. Such a sum can open a component
whose vertices have no unit-power edge to an earlier component. It enumerates
the possible direct-root component subsets in these finite frozen graphs,
closes each under available two-parent links, and chooses a reachable subset
with the lowest direct-root overhead in its stated call-count model. It then
emits each explicit two-parent witness before walking that component's
unit-power edges. The native loader checks these coefficient equations and
topological dependencies.

| Restarts | Requested seeds | Original calls | Root-first calls | Two-parent calls | Auxiliary calls |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 21 | 62 | 55 | 38 | **25** |
| 128 | 659 | 667 | 660 | 660 | **660** |

The [auxiliary planner](steiner_plan.py) examines the remaining direct roots
after two-parent linking. It finds two shared vertices, `(-3,0)` and `(0,-5)`,
reachable from already constructed points by unit-power edges. Their unit-power
edges construct the three remaining roots. Its finite mask search selects a
two-vertex cover from candidates reachable in one step from the existing graph
and able to reach a remaining root in one step. The
one-restart plan therefore has one direct root, 22 edges, and 23 constructed
vertices for 21 requested seeds. The loaded-plan validator bounds auxiliary
vertices, checks every coefficient equation, and requires every requested
seed. The [plan](steiner-plan-1.json), [count receipt](steiner-1-receipt.json),
and [native replay](steiner-local-replay.json) freeze this candidate. For 128
restarts the [plan](steiner-plan-128.json) is identical to the root-first plan.

The count includes calls in direct-root construction, including calls whose
left operand is the identity, plus one call per graph edge. It excludes the
shared binary-power preparation, normalization, graph search, and evaluation.
The [one-restart](root-first-1-receipt.json) and
[128-restart](root-first-128-receipt.json) receipts pin the input and output
plan hashes. The plans are [one restart](root-first-plan-1.json) and
[128 restarts](root-first-plan-128.json).
The two-parent receipts and plans are
[one restart](two-parent-1-receipt.json),
[128 restarts](two-parent-128-receipt.json),
[one-restart plan](two-parent-plan-1.json), and
[128-restart plan](two-parent-plan-128.json).

The [root-first replay](root-first-local-replay.json) and
[two-parent replay](two-parent-local-replay.json), and
[auxiliary replay](steiner-local-replay.json) each invoke both native planned
evaluators on the original Q and four independently constructed Q values. They
checks every frozen point in the one- and 128-restart streams plus the
alternate one-restart points. These local invocations provide correctness and
operation-count evidence; wall-time comparison remains in the Tier 1 paired
panel. The [existing Lean graph proof](../prime-j0-eisenstein-residue-20261015/JointSeedGraph.lean)
proves the unit-edge and two-parent coefficient-to-point implications used by
the emitted edges, under its stated additive and unit-action hypotheses. The native replay
checks the concrete secp256k1 implementation.

To regenerate the plans from the frozen source artifacts:

```sh
python3 root_first_plan.py \
  --source ../prime-j0-eisenstein-residue-20261015/rho-joint-graph-plan-1.json \
  --output root-first-plan-1.json --receipt root-first-1-receipt.json
python3 root_first_plan.py \
  --source ../prime-j0-eisenstein-residue-20261015/rho-joint-graph-plan-128.json \
  --output root-first-plan-128.json --receipt root-first-128-receipt.json
python3 two_parent_plan.py \
  --source root-first-plan-1.json \
  --output two-parent-plan-1.json --receipt two-parent-1-receipt.json
python3 two_parent_plan.py \
  --source root-first-plan-128.json \
  --output two-parent-plan-128.json --receipt two-parent-128-receipt.json
python3 steiner_plan.py \
  --source two-parent-plan-1.json \
  --output steiner-plan-1.json --receipt steiner-1-receipt.json
python3 steiner_plan.py \
  --source two-parent-plan-128.json \
  --output steiner-plan-128.json --receipt steiner-128-receipt.json
```

The plans are compatible with the existing
`--pilot-rho-restart-joint-graph-planned` and
`--pilot-rho-restart-joint-fused-graph-planned` commands. A future Tier 1
panel should add the root-first plans as distinct frozen arms, with a same-Q,
same-scalar paired comparison and the usual calibration and noise gates.
