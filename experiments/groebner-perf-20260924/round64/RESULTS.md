# Prepared independent-field checker results

The final local correctness and artifact audit pass. No timing query was
admitted, so neither the squaring tables nor packed multiplication has an
established complete-query speedup from this run.

| Check | Result |
| --- | --- |
| Unit groups | 16 passed |
| Three-arm preflight records | 138 |
| Verified records | 60, including 30 complete PDP queries |
| Retained algebraic budget failures | 78 |
| Distinct independently audited algebraic proofs | 7 |
| Source/generated/binary/resource bindings | 211 |
| Measured source files | 175 |
| Qualified timing trials / queries | 0 / 0 |
| Admission | 2 rejected; 31 trials unrun |
| One-minute load / frozen limit | 37.1245 / 14 |

Validation ran on Apple M4 Pro ARM64, macOS 26.6, Python 3.13.1, with native
dependencies rebuilt in optimized and UBSan modes. Exhaustive degree-1..5
fields, monomial-basis products, randomized fields and byte/power-of-two
boundaries through degree 129 agree with the reference arithmetic. Packing
controls extend through 255 input coefficients. A 256-coefficient carry
counterexample establishes why the explicit upper bound is necessary.

Fresh native witnesses match the Python producer for degrees 3/5/9/31/63 in
both native build modes. Every archived successful public-point witness passes
both prepared checkers. Altered points, intermediates, slopes and equations
fail. The checker also passes with inversion, lifting and point addition
forbidden. No producer arithmetic is used to validate a witness.

All full-query arms preserve the round63 basis, proof, first assignment,
extraction counts, curve witness and logical solver/checker counters. Native
witness production is the same in every arm, including fresh sign search.
The field validation and prepared tables are outside the charged query
interval for every arm; all target-dependent field operations are charged.

Degree-31 reachable tuple/integer storage for tables and masks was 38,056 bytes
for squares and 77,212 bytes for packed on this interpreter. These measurements
are neither incremental allocation nor process RSS. The tables contain 1,024
squaring entries per arm, plus 1,024 reduction entries in packed. Setup is not
amortized into a multi-target result.

The first attempt passed all arithmetic/witness groups but failed a synthetic
statistics test that still named the preceding experiment's primary arm. Its
source snapshot and logs are retained. The corrected test derives its primary
arm from the frozen plan. No timing ran in that failed attempt.

`results/` retains the final build receipt, preflight, rejected timing panel,
independent audit, logs, source snapshot, profiles and prior failure. The final
plan SHA-256 is
`baf0f087bcf1deb1090d2576e23730c7d4d07e53a5e60261ea49e7551eb073be`.
Linux/macOS CI measurements remain pending. No backend-routing, GPU-speedup,
full IC/rho, natural-yield or asymptotic-algorithm claim follows from these tests.
