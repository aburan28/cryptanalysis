# Compressed automorphism orbit for the hex scalar tree

The fixed-base secp256k1 evaluator selects at most sixteen points from a
174,883-entry affine table. The previous gauge tree delays automorphism
actions and pays for field multiplications when subtrees change gauge.
This experiment materializes the automorphism orbit in a 96-byte entry:
`(x, m, y)`, where `m = x + beta*x = -beta²*x`. A lookup reconstructs
the three x-coordinates as `x`, `m - x`, and `-m`, applying the sign to y.
All selected points are then actual global-gauge points. The same frozen
tree shape joins them with gauge zero at every node.

`make_plans.py` transforms each of the preceding 969 plan records by
retaining its join indices, setting join gauges and runtime rotations to
zero, and independently replaying the weighted join-path score. The
46,512-byte plan table is unchanged in size. `native_overlay.py` makes
the 96-byte table and plan changes in a disposable native source tree;
the committed parent evaluator remains unchanged. The checker verifies
every output point against independently generated secp256k1 coordinates,
the zero-rotation invariant, table memory, operation-model work, and
formula-DAG depth.

The additional retained table memory is exactly 174,883 × 32 = 5,596,256
bytes. Table construction invokes one Solinas multiplication for each
entry to form `beta*x`; that target-independent preparation belongs in
cold-start accounting. The online arithmetic model removes one field
multiplication per frozen runtime gauge rotation. It also adds at most
one field subtraction for selecting a nonzero automorphism image; memory
traffic and cache effects must be measured in the complete operation.

`OrbitCompression.lean` proves the two-coordinate reconstruction from
the additive group laws and the exact root relation
`x + beta*x + beta²*x = 0`. It also proves the full-binary-tree join-work
formula: for n≥2 affine leaves, the ordinary 6/10/14-call formulas use
`10n - 14` join calls for every tree shape. The Lean declarations are
`reconstruct_beta`, `reconstruct_beta_sq`, and `join_work_nonleaf`.
The pinned Lean toolchain and checked outputs are retained in
`lean-receipt.json`. The Rust-to-Lean field representation and formula
bridge remains open; native point replay and call instrumentation cover
the executed code separately.

The preceding 512-scalar holdout is a calibration panel known during
design. The source, plan, native binary, and calibration evidence are
committed before a new disjoint 512-scalar holdout is generated from the
source commit. A controlled CPU timing claim requires the repository's
isolated-host receipt.

Reproduce the existing calibration checks:

```sh
python3 experiments/prime-j0-hex-orbit-materialized-20261013/make_plans.py
python3 experiments/prime-j0-hex-orbit-materialized-20261013/check.py \
  experiments/prime-j0-hex-dag-pareto-20261013/holdout.json \
  experiments/prime-j0-hex-orbit-materialized-20261013/calibration-native.jsonl
cd experiments/prime-j0-hex-orbit-materialized-20261013 && lean OrbitCompression.lean
```
