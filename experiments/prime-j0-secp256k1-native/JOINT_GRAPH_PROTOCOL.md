# Co-designing the pair graph and representative selector: frozen protocol

## Candidate

Keep the width-six digits, 13-column comb, nine norm-ranked Eisenstein
representatives, balanced 72-byte affine pair slots, and exact
maximum-matching row atlas. Store 33 complete pair edges among the 12
ordinary rows. Begin with all 30 edges of row distance at most three.
Add three distinct long edges by a frozen greedy rule: at each step,
evaluate every unused edge on the design panel, and choose the edge
minimizing the total graph-aware point proxy after the nine
representatives have been reselected for that proposed graph. Break
ties by lexicographic edge order. This co-design uses the same
93,533,616 retained pair-table bytes as graph33. The online selector
computes the same 13 masks per representative and uses the chosen
graph's 4,096-entry atlas; no extra representatives or table points are
introduced. This is a variable-time public-scalar method.

## Inputs and gate

Draw a 2,048-scalar design panel with `random.Random(20261009421)` and a
disjoint 4,096-scalar holdout with `random.Random(20261009422)`, each
uniform from `[0,n)`. The parent graph-aware release binary has SHA-256
`fbd46d82b7b7867b4bf71dedc46b8ef8a43dd552a94b3779158b347ee1e40b80`.
Score each valid representative using

`5 * tau_steps + 11 * (unfused_mixed_additions - matching_cardinality)`,

including the sparse top-row repair. Ties in representative selection
use the existing norm rank; ties in matching use the lexicographically
smallest edge sequence. Check the first 128 cases of each panel against
the parent native selector's representative, tau count, repair, pair
fusions, and mixed additions. Preserve every per-case delta, both scalar
input hashes, graph and atlas hashes, raw failures, and table size.

Implement the new graph only if the untouched holdout proxy falls by
at least 0.5% against parent graphaware33 and the 33 tables fit within
90 MiB. Report scalar regressions and zero-gain cells even when the
aggregate passes. The native gate then compares exact outputs,
representatives, tau counts, repairs, and fusions on five boundary
values, 214 prior frozen inputs, all 129 expected-point fixtures, and
both new panels, with at least 256 independently computed points.
Direct group sums for every new edge and atlas disjointness for all
4,096 masks must pass. Keep the old mode as the paired baseline.

The point proxy counts ordinary tau and mixed-addition field products.
It omits recoding, table lookup, cache effects, and exceptional point
paths. Full online CPU speed requires an isolated-host paired receipt
charging all nine recodings, graph-aware scoring, point work, and final
verification. The currently available RunPod pod does not pass the
host-level isolation preflight.
