# Adaptive path matching for the fixed-generator tau comb: frozen protocol

## Candidate and baseline

The candidate adds pair tables for the five odd adjacent row edges
`(1,2),(3,4),(5,6),(7,8),(9,10)` to the six even adjacent edges of
the existing paired-row comb. In each of the 13 columns, traverse active
rows `0..11` from left to right. Fuse rows `i,i+1` when both are active,
then advance two rows; otherwise evaluate row `i` alone and advance one.
This greedy rule gives a maximum-cardinality matching on the induced path.
The sparse top row and its repair are handled afterward as before.

The baseline is commit `20a5b880` (PR #530): six disjoint even edges,
three-limb compact affine points, nine-representative hex9 selector.
Each additional edge stores `81 * 81 * 6 = 39,366` compact points. The
candidate may retain no more than 11 such edge tables, or 45 MiB of slots
at 104 bytes each. The online timer, when available, must include the
matching decision, table access, decoding, point evaluation, affine output,
and every scalar-dependent recoding step. Table preparation is separate.
This is a variable-time method for public scalars.

## Independent screen and acceptance

Before native implementation, reconstruct the exact width-six digit stream
from each native selected representative. Use `random.Random(20261009161)`
to draw 2,048 public scalars uniformly from `[0,n)` for the design panel,
and `random.Random(20261009162)` for a disjoint 2,048-scalar holdout panel.
Compare six-edge matching, eleven-edge path matching, and the all-edge
complete-graph matching upper bound on exactly the same selected streams.
The complete graph is an operation-count bound, not an implementation or a
claim of practical storage. Record all per-panel fusion totals, the point
proxy `5*tau_steps + 11*mixed_adds`, active-row counts, and table bytes.

Proceed to the native path candidate only if holdout point proxy falls by
at least 1% versus the six-edge baseline and the path has no scalar with
fewer fusions. If this gate fails, retain the screen result and stop this
candidate. For an implemented path candidate, require exact selected
representatives, affine points, tau counts, and predicted fusion counts
against the baseline on five boundary scalars, 214 frozen scalars, all 129
benchmark fixtures, and both fresh panels. Independently replay at least
256 fresh points and every fixture expected point. Run the native release
suite and direct pair-sum tests across all 11 edges. Preserve raw failures.

The 129-case, seven-repeat CPU panel must use the same public scalar and
expected point in each arm, with the strict host isolation and noise gates
in `docs/ISOLATED_BENCHMARKS.md`. Local operation counts and correctness
tests do not establish CPU wall-time gain. Evaluate preparation time and
memory separately. The algorithmic literature audit must compare this
graph schedule and symmetry quotient with prior fixed-base comb and joint
precomputation before an academic novelty statement.
