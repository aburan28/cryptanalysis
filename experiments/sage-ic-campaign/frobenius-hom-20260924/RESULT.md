# Local result: public Frobenius-isogeny evaluation

## Decision and accounting

**PASS_LOCAL** for the frozen public `phi(P)` workload. On supported Koblitz
curves, the patch calls the native NTL binary point map through the existing
Sage API. The baseline is the unmodified `hom_frobenius.py` method using
projective coordinate exponentiation and codomain construction. Both arms
invoke the same public isogeny object API and verify every output against
that baseline. Each paired trial records construction plus the first full
point batch as a cold total, and a second full batch through the same
isogeny as a warm result. The reported warm geometric means are over cell
speedups, not over a pooled subset of calls.

| Frozen run | Workload | Warm public-call result | Cold constructor plus first batch |
| --- | --- | ---: | ---: |
| `run-003` primary | Seven cells, degrees 19/67/131/163, powers 1/7/65 | **11.128x** geometric mean; min 2.410x | **10.376x** geometric mean |
| `run-003` confirmation | Three new-seed cells, degree 31/131, `a=0` and alternate modulus | **11.226x** geometric mean; min 3.672x | **10.526x** geometric mean |

The accepted run used 16 balanced arm pairs per cell and verified **291,200
timed Sage-point outputs**. The earlier candidate used separate seeds and
verified another 291,200 timed outputs, but failed a custom point-class
constructor-count test. That failure is retained and its timings are not
pooled with the accepted result. The preliminary `run-001` singleton and
batch comparison motivated this change; its batch API is a different call
boundary and is only diagnostic.

Correctness tests cover infinity, the order-two point, inverses,
unnormalized representatives, powers from zero through full-field and
beyond, alternate irreducible moduli, both Koblitz `a` values, non-Koblitz
binary curves, prime-field curves, and a custom point class after the
isogeny's guard was cached. The revised suite passed four test groups and
Sage's `hom_frobenius.py` passed all **116 doctests**.

Fresh-process degree-131, power-65, 4,096-point, six-call peak RSS was
**262,160,384 B** for the incumbent and **264,650,752 B** for the patch:
+2,490,368 B, or about 0.95%. This meets the frozen 5% memory limit.

This result speeds one Sage isogeny evaluation path. It does not establish
an end-to-end index-calculus or verified DLP speedup: the repository's
degree-131 IC reference uses separate ONB and SAT/F5 paths. Such a claim
needs a frozen workload, candidate/run IDs, every exclusive phase cost,
and a verified recovered logarithm under the repository's accounting rules.
