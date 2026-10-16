# Shared Eisenstein Q-seed graph

The graph builder reduces target-dependent Q-table construction for a batch
of rho restart points `aG+bQ`. The norm-4033 recoder requests points indexed
by Eisenstein pairs `(u,v)`, representing `uQ+vτ(Q)`. It creates only the
requested pairs. Each earlier point supplies its six unit rotations using
the curve's order-three automorphism and point negation. The builder first
tries a rotated earlier point plus `Q`, `−Q`, `τ(Q)`, or `−τ(Q)`; then a
rotated shared binary power; then a sum of two earlier rotated points. A
remaining isolated pair uses the direct binary-power construction. One batch inversion then
normalizes the unique graph vertices, and the same sparse Q table feeds the
shared Horner or fused-pair evaluator.

The frozen one-restart stream requests 21 Q digit seeds: eight use the direct
builder and 13 use graph edges. The frozen 128-restart stream requests
659 unique Q digit seeds: one uses the direct builder and 658 use graph edges.
The source-level `add_projective` call count for all requested seeds changes
as follows; both builders also prepare the same binary powers and batch
normalize the Q points:

| Restart count | Direct builder calls | Graph root calls | Graph edge calls | Graph total calls |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 113 | 49 | 13 | 62 |
| 128 | 4098 | 9 | 658 | 667 |

These are calls in the seed construction loops, including additions whose
left operand is the identity. They are not field-operation counts or wall
time ratios. The graph search and unit rotations also cost time and are
charged to the target. In particular, an unisolated local one-restart
invocation showed material search overhead; the operation reduction alone
does not establish an online gain. The graph builder retains the same Q table size as the sparse
builder: 453,204 bytes including global G and seed preparation for one
restart, and 519,556 bytes for 128 restarts. The transient six-unit orbit
index, graph, and batch-normalization vectors are absent from that retained
payload figure; their construction is charged to
`target_preparation_ms` in both new commands.

The [Lean graph module](JointSeedGraph.lean) proves that a direct seed, a
rotated-parent edge, and a two-parent rotated sum extend a valid
coefficient-to-point graph under explicit additive and unit-action map
premises. It also proves the four axis-neighbor coefficient relations. The
pinned [Lean receipt](joint-seed-graph-lean-check.json)
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
