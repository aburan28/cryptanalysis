# Result: public ONB inversion by extended Euclid

Accepted field SHA-256 in both copies:
`2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd`.
The parent is
`dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e`.
The polynomial Euclid routine matches the IC runner's already established
`AuditField.inv` approach. A canonical-input check confines it to valid
nonzero ONB representations. Zero and noncanonical raw input use the old
exponentiation route, preserving the API's prior behavior for those inputs.

| Warm public CPU operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 inversion | 6.12× | 6.01× |
| Degree 9 inversion | 11.43× | 12.92× |
| Degree 131 inversion | 127.52× | 105.89× |
| Degree 131 `pointFromX` | 39.30× | 39.49× |
| Degree 131 point doubling | 64.08× | 70.83× |

The benchmark used identical seeded inputs, 32 nonzero elements per degree,
24 abscissae, nine alternating matched rounds and exact output checks before
and during each timing round. The degree-131 public curve functions use
`Onb.inv`; the tracked IC runner's `AuditField` already overrides inversion,
so these ratios must not be assigned to its full pipeline.

| Fresh-process `pointFromX` median | Parent A | Candidate A | Parent B | Candidate B |
| --- | ---: | ---: | ---: | ---: |
| Valid abscissa | 5.074 ms | 2.186 ms | 8.634 ms | 1.500 ms |
| Invalid abscissa | 8.031 ms | 0.152 ms | 4.538 ms | 0.072 ms |

Each cold set used seven alternating fresh processes per variant and outcome.
Both sides inherited the adaptive Frobenius setup; the first valid recovery
built the exponent-2 table and the first invalid recovery built none. The
parent cold times varied substantially across the two sets, so these are
stage ranges, not a universal speedup.

The exact verifier matched **1,046** inverse and curve outputs under Python
3.9 and 3.13, including every nonzero degree-5 coordinate, random degree-9
and degree-131 elements, zero, selected noncanonical raw vectors, and curve
operations. Fourteen Python 3.9 artifact replay tests and three real Python
3.13 solver-independent runner IC tests passed. All eight inherited archive
verifiers passed locally with the new source pin.

The Python ONB work ran on the Apple Silicon CPU, not Metal. Complete verified
IC and DLP speedup remains **unknown** because the SAT-backed full runner and
calibrated complete-run accounting were unavailable locally.
