# Q1530 proof map

Q1530 computes finite consequences of Q1526's conditional uniform-query
law. It does not prove that law, N131 factor-base counts for W≤7/W≤8, or
rank novelty. Those are the explicit hypotheses of the work projection.

| Result | Lean declaration | Exact scope | Status |
| --- | --- | --- | --- |
| The N53 random table covers a smaller fraction of distinct keys than descriptor draws | `Q1530.n53_unique_key_coverage_below_descriptor_fraction` | 1,418,520 / 2,730,335 keys versus 2,000,000 / 2,743,068 descriptors | checked |
| W≤8 matrix proxy exceeds 2^61 | `Q1530.w8_matrix_exceeds_budget` | sampled W≤8 K=7,040,422,563, proxy 4K² | checked conditional arithmetic |
| W≤7 full-table quotient-reuse pair work exceeds 2^61 | `Q1530.w7_full_pair_additions_above_budget` | sampled W≤7 B/K, recorded r, `T+(263/262)Q` | checked conditional arithmetic |
| No eligible cell in the 84-cell sweep beats W≤7 full table | `Q1530.all_84_cells_have_at_least_w7_full_cost_when_matrix_eligible` | W5–W8, fractions 2^-j for j=0..20, matrix proxy 4K² | checked conditional arithmetic |

The fourth theorem uses kernel-checked `decide` over the complete finite
grid, cross-multiplying positive integer denominators. It includes W≤8
cells in the enumeration but excludes them from the minimum when the matrix
proxy exceeds the threshold. The [proof receipt](lean/proof_receipt.json)
pins Lean 4.35.0-rc4 and exact source/output hashes; all four
`#print axioms` checks report no axioms. `lean4checker --fresh` was
unavailable. The independent [validator](validate.py) recomputes each
rational cost and checks all source hashes.

The N53 rate comparison is an empirical calibration, not a formal theorem.
The mathematical statement used for its conditional prediction is
`p = B²/(2r) × distinct_key_coverage`. The coverage identity and exact
inputs are archived; the statistical interval uses the Wilson construction
for matched query positions. Since the two schedules and targets are not
independent cross-degree samples, this calibration does not prove the N131
query law.
