# Correlation-shaped path matching: frozen screen protocol

## Candidate

The existing adaptive τ-comb evaluator precomputes pair sums along the
numeric row path `0,1,...,11`. This screen keeps exactly eleven edge tables
and the same maximum-matching rule, but changes the order of the twelve
ordinary rows in that path. The chosen order is fixed for all future
scalars, independent of the scalar being evaluated. The sparse top row is
handled separately. Every row-pair table has 39,366 compact slots, so the
retained edge-table budget remains 45,034,704 bytes on the target build.

Draw 4,096 uniform public scalars in `[0,n)` with
`random.Random(20261009211)` for design. Obtain their selected Eisenstein
representatives from the frozen native nine-choice path binary, then
reconstruct the width-six digit streams independently. For each of 13 comb
columns, record the 12-bit active-row mask. Let `w(i,j)` be the number of
design columns where both rows `i,j` are active. Choose the undirected
Hamiltonian path maximizing the sum of its eleven edge weights, using an
exact Held-Karp subset dynamic program. Resolve equal weights by the
lexicographically smallest oriented row sequence. The path selection uses
no holdout data and no CPU timing.

Draw a disjoint 4,096-scalar holdout with
`random.Random(20261009212)`. Evaluate maximum-cardinality matching on
each active-row induced path by scanning that path left to right. Compare
the selected path against the numeric path and the complete-graph bound
on the same digit streams. Report fusion totals, point-operation proxy
`5*tau_steps + 11*mixed_additions`, table bytes, and the per-scalar change
distribution on both panels. Verify that the native numeric-path fusion
count equals independently reconstructed digits for every case.

Proceed to a native row-permuted candidate only if the holdout point proxy
improves by at least 1% over the numeric path with the same eleven-table
storage. If it fails, retain the screen and do not introduce a new native
mode. Any implemented mode must match all baseline affine points,
representatives, tau counts, and expected fusion counts on the frozen
boundary, fixture, design, and holdout inputs, plus independently verify
at least 256 fresh points and all 129 fixture expected points. A CPU
speedup requires the strict isolated-host panel; operation counts are
stage evidence only. This is a variable-time public-scalar method.
