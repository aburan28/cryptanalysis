# Cached-plan correctness map

The plan table changes when the tree is selected, not the group operation.
For a count triple, the builder runs the format-171 pair selector on abstract
nodes with the same gauges, affine/projective states, and product depths.
The online evaluator groups the actual selected points by gauge, then
executes the resulting sequence of joins. Each selected point appears once.
The format-171 Lean declaration
`PrimeJ0GaugeTree.reordered_tree_correct` in
`../prime-j0-gauge-tree-20261012/GaugeTree.lean` proves that any binary tree
with a permutation of the selected leaves gives their sum, assuming the
abelian group laws, additive order-three automorphism, and correct local
gauge alignment. Its pinned Lean 4.34.1 build and `#print axioms` audit are
in the parent experiment; the declaration uses only `propext`.

The 680-triple exhaustive test checks that the dense plan index is unique,
the stored length and storage size are exact, and every cached plan matches
the dynamic tree on real affine points, including its rotations and depth.
The frozen scalar panel and independent binary point path test the bridge
from the U14 recoder through the plan lookup to the concrete curve. The
source-level plan-index and Rust schedule are not kernel formalized; their
exhaustive domain check and point replay are recorded as implementation
evidence rather than Lean theorems.
