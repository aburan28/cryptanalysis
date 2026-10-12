# Selected-row equivalence and comparison contract

Forward elimination creates an echelon basis for the generated Macaulay row
space. Its pivot columns are distinct and immutable. A reducer with pivot c
has zero coefficients in all columns before c, even if later retained rows
have already been reduced. To reduce a selected row, inspect later pivot
columns in ascending order and XOR the corresponding reducer when necessary.
Each step clears that pivot and cannot restore any earlier pivot. The result
has its original leading pivot and zeros at every other pivot column. It lies
in the same row space, so uniqueness of reduced row-echelon form identifies
it with the reference fully reduced row.

The retained set is determined solely by divisibility of the pivot monomials.
Inspect pivots from the smallest monomial upward and retain one exactly when
none of the already retained leads divides it. This is the same test and
output order as the reference. Moving it before backward elimination therefore
preserves the output basis. This statement does not say a finite Macaulay
matrix is complete. Every emitted result still needs original-ideal derivation,
reverse membership, reducedness, critical-pair and Boolean-field-pair checks.
PDP controls additionally require independent equations and curve replay.

For r pivots, k retained rows and w coefficient words per row, the reference
tests r(r-1)/2 backward pivot entries; the candidate tests at most k(r-1).
Its row XOR bound is O(krw). Minimal-lead selection costs O(rk) for both
methods. Forward elimination, layout construction, graph pruning, independent
verification and the size of the necessary Macaulay matrix are unaffected by
this argument. There is no universal measured improvement or new bound for
general Gröbner computation; the ordering can change the actual number of XORs.

## Resource and proof accounting

All data dependent on coefficients, selected pivots and proofs is fresh per
query. Charge one work unit per column for selection-flag initialization
before allocating the flag vector, and charge the same divisor tests and
backward pivot inspections as executed. Existing XOR, proof-node, row, payload,
extraction and graph-pruning caps remain. Exhaustion discards the candidate;
F4 fallback receives the remaining producer and checker budgets.

The extra selection flags occupy one byte per column, at most 262144 bytes
under the existing layout limit. The pre-existing minimal-lead vector remains.
MatrixStats.peak_payload_words covers row coefficients only, excluding flags,
proofs and other metadata; process peak RSS is separately recorded. Moving
selection moves its time from extraction into elimination. Compare their sum
or the full producer interval, rather than interpreting either phase alone.

The Python model uses arbitrary-width integer rows and reconstructs the exact
proof graph independently of C++ word storage. It checks both successful and
budget-exhausted prefixes against the declared software work charges. These
charges are not calibrated instruction counts. The mathematical audit also
checks the resulting ideal and Boolean Gröbner completion independently of
the producer model. Coherent counter and proof mutations must be rejected.

## Frozen workload

The same 13 controls, input law, degree bounds, resource limits and 60-second
worker timeout are retained from round105. Use three arms: f4-quotient as a
coverage control, matrix-quotient as the baseline, and matrix-minimal as the
candidate. Every arm uses the same independent checker and output API as its
round105 counterpart. One warmup is followed by four rotating observations;
three arms cannot be perfectly position-balanced in four repetitions, which
is another reason these local timings are exploratory. All failures and
fallback costs remain in the report. No selected reruns are permitted.

The primary diagnostic is the complete query from fresh coefficient descent
through certification, bounded extraction, independent equations/curve replay
and lease teardown. Target-independent layout setup stays separate. This is
a frozen planted-control study; it is not a natural relation-yield estimate
or a one-target IC/rho comparison. Qualified and aggregate speedups stay null.
