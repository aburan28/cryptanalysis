# Solinas cube-root rotation for the compact tau table

Mode 155 keeps the 64-byte affine points, the proved sixteen-window tau
recoding, and the direct XYZZ bucket merge of mode 154. It computes the two
nontrivial cube-root x rotations with the fixed three-fold reduction in
`PROOF.md`. The retained table plus atlas is **8,336,528 bytes**; the new
three-word canonical constant array adds 96 bytes, for **8,336,624 bytes**
charged to mode 155.

The source and input law are frozen before drawing a disjoint 4,096-scalar
panel. Independent affine binary multiplication constructs expected points.
The candidate and five controls are replayed on that panel, ten boundary
cases, and 129 fixed cases. A temporary counter build records how many unit
rotations use the new reducer and the matched source-level product counts;
its patch and raw log are kept beside the result. The shipping source has
no counters.

The resulting operation counts and retained bytes are algorithmic
measurements. CPU wall-time comparisons require a passing host-level
isolation receipt as specified in `docs/ISOLATED_BENCHMARKS.md`.
