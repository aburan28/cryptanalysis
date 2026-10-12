# Proof map for the Pareto gauge tree

The addition tree reorders selected affine terms and changes each subtree's
gauge before joining. The inherited checked theorem
`PrimeJ0GaugeTree.reordered_tree_correct` in
`../prime-j0-gauge-tree-20261012/GaugeTree.lean` proves equality of the
represented point and the original leaf sum. It assumes an abelian group,
an additive automorphism `β` of order three, and a leaf permutation. The
Rust table uses each selected term exactly once; the 680-pattern and panel
point replays check that bridge on concrete secp256k1 inputs.

For the source operation model, a leaf is affine, every join returns a
projective point, and joins cost 6, 10, or 14 field products according to
their child types. The induction invariant is
`baseProducts(shape)+14 = 10*leaves(shape)+4*leafFlag(shape)`.
At any internal root, `leafFlag=0`, giving `10n−14`; rotations are charged
separately. Pareto pruning is sound because replacing a subtree with one
using no more work or depth cannot worsen either parent coordinate.

| Result | Lean declaration | Exact assumptions | Status |
| --- | --- | --- | --- |
| Reordered gauge tree represents the leaf sum | `PrimeJ0GaugeTree.reordered_tree_correct` | Abelian point group, order-three additive automorphism, exact leaf permutation | Checked in inherited module |
| Join formula cost identity | `PrimeJ0ParetoCost.joinProducts_identity` | Shape-dependent counts 6, 10, 14 | Checked |
| Base cost for every binary tree | `PrimeJ0ParetoCost.baseProducts_identity`, `joinedTree_cost` | Every leaf affine; every join returns projective | Checked |
| Pareto-pruning monotonicity | `PrimeJ0ParetoCost.dominatedSubtree_replacement` | Additive work, max-plus depth, fixed join and rotation costs | Checked |
| Exhaustive selection of the best plan under each depth cap | `plans.py` recurrence and 680-record replay | Three gauges, at most 14 leaves, stated costs and greedy cap | Finite generator checked; Lean formalization partial |

`ParetoCost.lean` imports `Lean` and uses pinned
`leanprover/lean4:v4.34.1`. `lean-build.txt` records the actual module build
and `#print axioms` audit: `propext` and `Quot.sound` are the only reported
foundations. There is no `sorry`, `admit`, custom research axiom, or native
evaluation bypass. `lean4checker --fresh` was unavailable.

The open formal obligation is a Lean encoding of the finite count-triple
frontier recurrence, the 42-byte plan decoder, and a refinement theorem from
those plans to the Rust join loop. The concrete secp256k1 field formulas,
endomorphism, exceptional branches, and Rust recoder are covered by native
correctness checks here, not by a kernel theorem. The checked cost identity
is a source formula model and does not include measured field latency or
the whole scalar call.
