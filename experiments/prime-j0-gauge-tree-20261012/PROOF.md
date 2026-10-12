# Gauge-aware tree proof

Let `β` be the secp256k1 automorphism `(x,y) ↦ (ζx,y)` for a cube root of
unity `ζ`. A node with gauge `g` stores a point `P` representing `β^g P`.
Before a join in gauge `t`, rotate each stored child by `β^(g-t mod 3)`.
Because `β³ = 1`, applying `β^t` after the join recovers the sum of the two
original represented points. Induction over the binary tree gives the sum of
all selected affine terms. Associativity and commutativity make the tree's
parenthesization and leaf order irrelevant. Thus the U14 sector recoding's
sum remains the same point.

For two affine points `A=(x₁,y₁)`, `B=(x₂,y₂)`, let `p=x₂−x₁`, `r=y₂−y₁`.
The specialized XYZZ join uses `ZZ=p²`, `ZZZ=p³`,
`X=r²−p³−2x₁p²`, and `Y=r(x₁p²−X)−y₁p³`.
Dividing `X` by `p²` and `Y` by `p³` gives the ordinary chord law when
`p ≠ 0`; the implementation handles doubling and inverse pairs separately.
The projective join is the existing XYZZ addition formula with canonical
Solinas products. Point tests compare both formulas to the prior evaluator.

## Lean proof map

`GaugeTree.lean` builds with `leanprover/lean4:v4.34.1` and imports `Lean`.
The theorem's abstract `G` is the point carrier; `add` is point addition;
`beta` is the automorphism. The precise assumptions appear in the table.

| Result | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| Gauge alignment | `PrimeJ0GaugeTree.align_correct` | `β³ = id` | Checked |
| Rotation distributes over addition | `PrimeJ0GaugeTree.rotate_add` | `β(x+y)=βx+βy` | Checked |
| One gauge-aware join | `PrimeJ0GaugeTree.join_correct` | Both properties above | Checked |
| Every binary tree represents its leaves | `PrimeJ0GaugeTree.evaluate_correct` | Both properties above | Checked |
| Reordered tree equals the original leaf sum | `PrimeJ0GaugeTree.reordered_tree_correct` | Both properties, associativity, commutativity, zero laws, leaf permutation | Checked |

Run `ELAN_TOOLCHAIN=leanprover/lean4:v4.34.1 lean GaugeTree.lean` here.
`lean-build.txt` records the build and axiom audit: each declaration depends
only on Lean's `propext`. No research axiom, `sorry`, `admit`, or native kernel
bypass appears in the theorem module. `lean4checker --fresh` was unavailable.

The formal tree theorem assumes that the selected leaves are a permutation of
the sector recoder's terms. The Rust selector constructs its leaves from those
terms once each, and the 4,096-point replay checks the implementation. A
kernel-level proof of the Rust selector, Solinas arithmetic, exceptional
branches, and concrete secp256k1 `β` homomorphism is still open; the prior
Solinas reduction theorem covers its integer fold separately.
