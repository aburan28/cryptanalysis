# Result: synchronize the IC runner ONB arithmetic

The runner field source now exactly matches the measured local source,
SHA-256 `7e9c9e14fcd215ec75414a43e28472fc206721be451f0a2e5c47b99c0676613c`.
The runner curve source is
`33a1a95a4b149d6cbcf6c53f5c4819706fd8d6f6c674f45b21fa812a99eff598`;
its only difference from the optimized local curve source is the pre-existing
`NormalView` class. The original runner sources are frozen beside these
measurements. In the IC runner, `AuditField` already overrides `inv` with
Euclid and `trace` with coordinate parity, so the benchmark uses those same
operations on both sides without audit-counter overhead.

| Warm degree-131 CPU operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| Field multiplication | 2.26× | 2.71× |
| Frobenius exponent 1 | 8.60× | 8.11× |
| Coordinate packing | 30.94× | 30.17× |
| Coordinate extraction | 60.94× | 58.81× |
| Mixed `pointFromX` | 4.86× | 5.19× |
| Point doubling | 2.25× | 2.15× |

The benchmark uses identical seeded values, 48 field inputs, 24 mixed point
recovery inputs, seven alternating paired rounds, and output equality before
and during each timing round. These are isolated operations without audit
counter cost. They do not establish an end-to-end IC speedup.

Cold point recovery is slower. Seven fresh processes per side and outcome
gave medians of **2.899 ms candidate versus 1.799 ms incumbent** for a valid
abscissa, and **0.680 ms candidate versus 0.094 ms incumbent** for an invalid
one. The candidate builds one or two Frobenius byte tables on those first
calls. Their setup and memory costs need to be charged in a complete run.
The full runner lacks the SAT dependency locally, so no recovered logarithm
or full phase total was measured here.

The verifier matched **4,152** old/new field, curve and `NormalView` outputs
under Python 3.9 and 3.13. Three real solver-independent runner IC tests and
14 Python 3.9 artifact replay tests passed. The runner's existing `AuditField`
uses `int.bit_count` and is not Python 3.9 compatible; the Python 3.9 exact
comparison covers the underlying ported field and curve code through a
compatible parity surrogate, while the real runner tests used Python 3.13.

The Python ONB path runs on the Apple Silicon CPU, not Metal. Complete verified
IC and DLP speedup remains **unknown** pending SAT-backed runs with exclusive
phase costs and a calibrated operation unit.
