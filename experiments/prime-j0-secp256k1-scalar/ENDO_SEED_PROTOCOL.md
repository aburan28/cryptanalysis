# Endomorphism-assisted single-use width-four seed preparation

Freeze this protocol and `endo_seed_prep.py` before generating 64 new
one-use secp256k1 base/scalar pairs. Compare the existing explicit nine-seed
Jacobian chain with one change to two seeds, using the same width-four
digit stream, unit orbit table, and paired-stride evaluator. Independently
verify every seed point and final scalar product against Sage, and save
the checked Sage runtime receipt before execution.

Write `ω(P)=(βx,y)` and `τ=1−ω`. The published nine coefficient points
include `1+τ=2−ω` and `1−2τ=2ω−1`. Given the already-constructed `2P`,
compute

- `(1+τ)P = 2P−ω(P)` using one affine-base rotation and one mixed add;
- `(1−2τ)P = ω(2P)−P` using one projective-X rotation and one mixed add.

The current chain instead constructs `(1+τ)P` as `τP+P` and
`(1−2τ)P` via one generic Jacobian add. The two substitutions save
`3M+2S` and `3M+1S` respectively under the explicit source formulas.
The old complete preparation is `102M+43S+1I`; the proposed complete
preparation is `96M+40S+1I`, including eight-point batch normalization
and preparation of nine unit orbits. The online scalar evaluator should
have identical counts. These are generic source counts; multiplication by
`β` is charged as one field multiplication. If exceptional arithmetic,
incorrect seed points, or output mismatch occurs, retain the failure and
do not report a saving.

The primary diagnostic is complete one-use `M+S` plus a separately
accounted inversion, per paired scalar. The count excludes recoding,
allocation, verification, and CPU wall time. A native complete operation
with the field kernel and isolated host receipt is required for a CPU
speedup claim. Algebraic rewrite of known seed points and a mixed-add
chain do not establish academic novelty. The published width-four
method remains [Xu et al.](https://eprint.iacr.org/2024/1906).
