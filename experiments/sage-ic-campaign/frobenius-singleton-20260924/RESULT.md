# Local result: direct native binary Frobenius singleton

## Decision and boundary

**PASS_LOCAL** over PR #78 for repeated public `phi(P)` calls on the same
Koblitz/NTL guard. Both paired arms use the same newly built native binary;
the incumbent Python method calls its unchanged batch routine and the
candidate calls the added context-safe singleton. A fresh isogeny object is
constructed for each cold trial. Warm timing covers a second full mapped
point batch, with exact output checks in both arms.

| Frozen run | Workload | Warm public-call result | Cold constructor plus first batch |
| --- | --- | ---: | ---: |
| `run-002` primary | Six cells, degrees 19/67/131/163, powers 1/7/65 | **1.251x** geometric mean; min 1.164x | 1.224x geometric mean |
| `run-002` confirmation | Three new-seed cells, degree 31/131, `a=0` and alternate modulus | **1.154x** geometric mean; min 1.086x | 1.209x geometric mean |

The accepted run used 16 balanced arm pairs per cell and verified **257,920
timed Sage-point outputs**. A preliminary five-cell profile was only an
upper-bound diagnostic: its direct-prepared Python call failed after NTL
switched fields. The failure is retained in `tests-hom-v1.log`; none of its
timings enter the accepted result. The revised native helper restores the
correct NTL context before coordinate extraction, then uses the standard
Sage point layout for the output.

The revised public test suite passed four groups covering standard and
custom points, exception cases, alternate modulus, non-Koblitz and prime
fallback, and powers at the field boundary. The native suite passed two
groups including alternating field degrees and unnormalized points. Sage's
`hom_frobenius.py` passed all **116 doctests**. The Cython module built
successfully from the archived native source; its installed binary hash is
recorded in `install-002/install.json`.

Fresh-process degree-131, power-65, 4,096-point, six-call peak RSS was
**264,962,048 B** for the PR #78 path and **264,192,000 B** for the
singleton, a reduction of 770,048 B.

This measures Sage isogeny point evaluation, not a complete index-calculus
or recovered-DLP speedup. The local IC reference uses separate ONB and
SAT/F5 paths. Integrating either path requires a frozen candidate/workload,
all exclusive phase costs, and a verified recovered logarithm before an
end-to-end speedup can be claimed.
