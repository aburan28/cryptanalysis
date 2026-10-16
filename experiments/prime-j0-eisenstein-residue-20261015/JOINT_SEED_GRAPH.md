# Shared Eisenstein Q-seed graph

The graph builder reduces target-dependent Q-table construction for a batch
of rho restart points `aG+bQ`. The norm-4033 recoder requests points indexed
by Eisenstein pairs `(u,v)`, representing `uQ+vτ(Q)`. It creates only the
requested pairs. When an earlier requested pair is one coordinate away, it
adds `Q`, `−Q`, `τ(Q)`, or `−τ(Q)` to that point. An isolated pair uses the
existing shared binary powers of `Q` and `τ(Q)`. One batch inversion then
normalizes the unique graph vertices, and the same sparse Q table feeds the
shared Horner or fused-pair evaluator.

The frozen one-restart stream requests 21 Q digit seeds: 20 use the direct
builder and one uses a graph edge. The frozen 128-restart stream requests
659 unique Q digit seeds: 22 use the direct builder and 637 use graph edges.
The source-level `add_projective` call count for all requested seeds changes
as follows; both builders also prepare the same binary powers and batch
normalize the Q points:

| Restart count | Direct builder calls | Graph root calls | Graph edge calls | Graph total calls |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 113 | 106 | 1 | 107 |
| 128 | 4098 | 115 | 637 | 752 |

These are calls in the seed construction loops, including additions whose
left operand is the identity. They are not field-operation counts or wall
time ratios. The graph builder retains the same Q table size as the sparse
builder: 453,204 bytes including global G and seed preparation for one
restart, and 519,556 bytes for 128 restarts. Its temporary graph and batch
normalization vectors are target preparation costs and are charged to
`target_preparation_ms` in both new commands.

The [Lean graph module](JointSeedGraph.lean) proves that an edge extends a
valid coefficient-to-point graph under an additive evaluation map, that a
directly checked seed can be inserted, and that the four searched neighbors
have the required coefficient relation. The pinned [Lean receipt](joint-seed-graph-lean-check.json)
records the fresh build and `#print axioms`. The concrete Jacobian and field
operations are checked by native exact-output replay; a Lean refinement of
those machine operations remains open.

The local ARM64 [replay](joint-q-graph-local-replay.json) checks 942 exact
outputs in 40 serial commands, including the original and graph builders,
four alternate Q choices, and equal-point, opposite-point, zero-scalar, and
one-sided edge cases. The new commands are `--pilot-rho-restart-joint-graph`
and `--pilot-rho-restart-joint-fused-graph`; both charge graph construction
inside `online_ms`. The [Tier 1 plan](RHO_JOINT_BENCHMARK_PLAN.md) pairs them
with OpenSSL and with the existing direct sparse variants on the same frozen
restart stream. Linux source transfer and the serial Pod panel are pending
the previously requested approval.
