# Pareto gauge trees for fixed-base secp256k1 multiplication

Format 173 uses an exact finite work/depth search to select a gauge-aware
addition tree for each of 680 possible 14-term gauge-count patterns. On the
frozen 4,096-scalar panel it uses **526,168 modeled ordinary-path field
products**, 2,804 fewer than format 172, while keeping every pattern at or
below format 172's modeled dependency depth. Its 28,560-byte plan table
replaces the prior plan table, so retained table, constants, and plan data
remain **64,342,768 bytes**.

| Frozen panel measure | Format 172 cached greedy tree | Format 173 Pareto tree |
| --- | ---: | ---: |
| Scalars | 4,096 | 4,096 |
| Active affine terms | 57,343 | 57,343 |
| Gauge rotations | 12,886 | 10,082 |
| Modeled ordinary-path field products | 528,972 | 526,168 |
| Sum of modeled product depth | 201,965 | 200,505 |
| Retained table, constants, and plans | 64,342,768 B | 64,342,768 B |

The source model gives every binary tree of `n ≥ 2` affine terms a base cost
of `10n − 14` field products under the implemented affine-pair, mixed, and
projective XYZZ formulas. Gauge rotations add one product each. The new
search saves 21.76% of the prior panel's gauge rotations. It reduces the
panel's modeled field-product count by 0.530%; no online wall-time ranking
is inferred from that count.

The release tests matched all 680 gauge-count patterns on actual affine
table points and all 4,096 scalar records to format 172. The first 128
panel points also matched independent binary multiplication. The release CLI
matched every scalar, generator, output point, mode, and verification field
in the independent 129-case fixture. `plans.py --check` reconstructed the
frozen plan table and panel totals; `receipt.json` binds the code, inputs,
binary, tests, plans, and proof sources.

`ParetoCost.lean` checks the field-product invariant and dominance-pruning
rule with Lean 4.34.1. The inherited `GaugeTree.lean` proves that a reordered
gauge-aware tree represents the same point under the stated group and
automorphism assumptions. `PROOF.md` maps the formal results and remaining
implementation bridge.

The next measurement is a paired complete-operation format-172/173 replay
on a host passing the CPU isolation preflight, with the same source snapshot,
scalar panel, resource envelope, and prepared table. The current RunPod pod
fails that preflight; its CPU timings remain exploratory.
