# Compact affine storage for the sixteen-window tau evaluator

The new native mode 154 stores one affine `(x, y)` point per atlas seed and
window. It uses the same proved sixteen-window tau recoding and direct XYZZ
bucket merge as mode 153. When a selected unit rotates the x coordinate by a
cube root, mode 154 computes that product instead of loading the third stored
field element used by mode 153.

The table has 107,814 slots. Its 64-byte point payload and the unchanged
width-eight and width-nine atlases retain **8,336,528 bytes**, a reduction of
3,450,048 bytes from the two-X format. The two formats share the exact digit
recurrence and selected points; their difference is the storage and arithmetic
used to form each selected unit image.

The source and input law are frozen before drawing a new disjoint 4,096-scalar
panel. An independent affine binary implementation constructs expected points.
The candidate and four controls are replayed on those scalars, ten boundary
cases, and 129 fixed fixture cases. A separate temporary counter build counts
point-kernel field operations on the matched panel; its patch and raw log are
retained alongside a verifier. The shipping source contains no counters.

Operation counts and retained bytes describe an algorithmic tradeoff. CPU
wall-time comparisons require a passing host-level isolation receipt as
specified in `docs/ISOLATED_BENCHMARKS.md`.
