# Prepared constant-identity witnesses (kernel experiment)

The round65 physical-M4 exploratory profile puts approximately 8.48 ms into
constant-identity checking on the 27-variable fixture, compared with 1.85 ms
for the independent GPU transform's two copies. This experiment prepares
fresh constant witnesses once per check and then scans coefficient slices
without repeating the symmetry branch. Two portable C++ parity expressions
allow the compiler to vectorize the loop. The original loop remains the
reference. This is not yet connected to the complete-query checker.

The kernel assumes the caller has already validated proof extent and equation
bits and independently established which symmetry aliases may be skipped.
Every workspace word is overwritten for each check; at most 16 MiB is retained.
The result preserves acceptance, the first failing feature, and the exact
prefix of avoided-parity accounting, including zero and alternative witnesses.
It never reads a producer's coefficient table.

Promotion requires exact controls, fresh full-query comparisons against
round65, original-ANF auditing, portable/native rebuilds, and the repository's
host-isolation receipt for any controlled CPU speedup claim. No performance
claim, automatic routing change or asymptotic improvement is established here.
