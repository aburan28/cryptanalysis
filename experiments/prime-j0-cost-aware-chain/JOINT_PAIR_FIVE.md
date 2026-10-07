# Certified five-neighbor Eisenstein scalar reduction

The bounded pair evaluator currently reduces a public scalar through a
25-candidate search around a rounded GLV lattice point. The
[certificate producer](make_joint_pair_five_design.py) proves that
five candidates give the **global minimum** in the same L1 coordinate
metric on each exact study curve: the rounded center and its four
axial lattice neighbors.

Let `b1,b2` be the lattice basis and `R` the residual after rounding
both lattice coordinates. Then `R = s b1 + t b2` for
`|s|,|t| ≤ 1/2`. Convexity of the L1 norm gives

`||R||₁ ≤ M = max(||b1+b2||₁, ||b1−b2||₁)/2`.

For any lattice translation `V` with `||V||₁ ≥ 2M`, the triangle
inequality gives `||R−V||₁ ≥ ||V||₁−||R||₁ ≥ ||R||₁`, so the center
is at least as good. The inverse basis bounds the coefficients of
every `V` shorter than `2M`. Exhaustive integer enumeration within
those proved bounds leaves only `±b1` and `±b2` on both curves.

| Curve | `2M` | Short nonzero translations | Candidate costs evaluated |
| --- | ---: | --- | ---: |
| `glv-j0-32` | 8,873 | `±b1`, `±b2` | 5 instead of 25 |
| `j0-56` | 463,138,171 | `±b1`, `±b2` | 5 instead of 25 |

The [frozen design](joint-pair-five-design.json) retains the exact
basis, determinant, coefficient bounds, enumerated short vectors,
input hashes, and old tie order. The earlier 16,384 training scalars
per curve chose the same representative under both searches. That
agreement is a diagnostic; the bound above is the correctness
argument for every scalar on these exact curves.

The experiment will compare a five-neighbor evaluator with its
25-neighbor control on fresh disjoint inputs, using the same prepared
point tables and both serial and affine-wavefront online paths.
Local CPU timings remain exploratory until a host-level isolation
receipt exists. Nearest-plane GLV reduction is established prior art;
this curve-specific cutoff certificate is not an academic priority
claim.
