# Lazy host construction of a Metal nullspace

The accepted round49 host reconstructs every consistent GPU branch's lifted
nullspace before deciding how to solve it. Only the `nullity < y` path consumes
those vectors. The other path uses projection/Macaulay certificates and exact
original-variable enumeration from the equation columns.

This opt-in candidate constructs nullspace vectors only when `nullity < y`.
It retains the existing O(rank) pivot-row validation. The old loop's
`k == nullity` check is equivalent to `popcount(pivot_mask) == rank`, since
`k` counts all nonpivot feature columns. That check runs even when vector
construction is skipped. The small-nullity path also retains its old check.

The GPU shader is byte-for-byte round49's unrestricted affine shader, so this
experiment isolates the host change. The round50 restriction is a separate
candidate with an unresolved work tradeoff. The CPU implementation, native
interfaces, proof format, statistics, budgets, symmetry handling, original
equation checks, curve replay and independent round48 verifier are preserved.

For the three 27-variable fixtures, y=9 gives 45 lifted features. With 31
equations the rank is at most 31, so nullity is at least 14. Their host
nullspace-vector construction is therefore always unused. This structural
bound does not establish an elapsed-time speedup.

## Validation and measurement

`test_nullspace_boundary.py` independently enumerates five small controls:
nullity above, equal to and below y; full rank; and inconsistency. It compares
roots, bases, proof bytes and all integer counters with round49, with partial
production and GPU projection enabled and disabled, CPU optimized, UBSan and
actual Metal where available. The small-nullity controls must still execute
lifted enumeration. Existing proof, lifecycle, factory isolation and budget
tests remain in the suite.

`validate_native.py` runs the frozen 6,001-system corpus and 18 complete-query
inputs. `audit_queries.py` independently verifies every original-ANF proof,
complete root set and reduced basis. The raw GPU witness oracle remains the
accepted round49 oracle because the device kernel is unchanged.

`measurement_plan.json` freezes paired comparisons against accepted CPU and
tile16 Metal queries and round49 full/tile16 Metal. All arms rebuild fresh
coefficients and retain complete independent checking and signed curve replay.
Setup is separate; failed admissions and attempts remain results. Correctness
passes and work bounds do not establish speedups. Keep the candidate opt-in
until qualified complete-query measurements justify a routing change.

This establishes no general F4/F5 ranking, new asymptotic algorithm or verified
single-target IC/rho comparison. Candidate and online-speedup fields remain null.
