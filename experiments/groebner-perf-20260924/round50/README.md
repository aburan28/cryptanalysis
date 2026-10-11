# Restricted GPU affine projection

This opt-in experiment restricts the second Metal reduction introduced in
round49. The first lifted RREF, its output, the host producer, complete-query
semantics, work limits and independent round48 checker are unchanged. CPU
execution remains available; requested Metal failures remain explicit.

The native producer includes the accepted round49 implementation. The Python
adapter loads private round49 factories and changes only their native-library
directory. Separately loaded accepted comparators retain their own factories.

## Exact reduction

In the first RREF, each quadratic pivot column is zero in every other row.
An affine consequence has zero in that column, so its coefficient on that
quadratic-pivot row must be zero. Discard those rows. The remaining nonzero
rows comprise at most `y <= 10` linear-pivot rows and constant-one rows.
Retain exactly one representative constant-one row: feature-only RREF can
leave duplicates. The regression with `y=1`, seven equations and packed
columns `[58,38]` exercises this case.

Quadratic elimination on this smaller subsystem, skipping the original
quadratic pivot columns, yields exactly the complete affine consequence
space. Every row carries its original-equation combination witness. The
reported quadratic rank is the number of original quadratic pivots plus
the restricted quadratic rank. The rank in affine variables is the rank
from the restricted reduction. Constant rank remains a separate flag.

All original lifted output is written before restricting rows. Every
dispatched projection slot is overwritten on each call. The interface,
output sizes, symmetry representatives and synchronization remain unchanged.
The extra projection buffer is still 22 MiB for the 27-variable shape.

## Validation and performance

`test_projection.py` independently reconstructs each GPU row from the original
equations and compares the entire affine space and both ranks. It covers
random, exhaustive small, duplicate-unit and actual original-ANF cases.
The inherited adversarial tests cover lifecycle, factory isolation, proof
rejection, budgets, partial completeness, wide equations and CPU fallback.
`validate_native.py` exercises the frozen 6,001-system corpus and 18 complete
queries with projection and partial production enabled and disabled.
`audit_queries.py` separately replays every complete proof from original ANFs.

Correctness is not a speedup measurement. Complete-query comparisons must
retain transfers, proof construction, independent checking and curve replay;
setup is separate. This experiment makes no general F4/F5 ranking, novel
asymptotic or single-target IC/rho claim. Candidate and online-speedup fields
remain null until the applicable complete-pipeline measurement gates pass.
