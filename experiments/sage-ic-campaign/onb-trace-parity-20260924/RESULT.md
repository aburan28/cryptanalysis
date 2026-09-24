# Result: ONB trace through coordinate parity

Accepted `field.py` SHA-256:
`7e9c9e14fcd215ec75414a43e28472fc206721be451f0a2e5c47b99c0676613c`.
The parent is
`191584f34e0092922cf8747d075a0791df702b6153923285b48736d96b0c6c03`.
For canonical ONB vectors the absolute trace equals the parity of the
normal-basis coordinate weight. The source checks that an input is canonical
before using parity, then retains the original Frobenius-sum loop for other
raw vectors. This preserves their previously observable results.

| Warm operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 trace | 4.15× | 5.14× |
| Degree 9 trace | 5.72× | 5.65× |
| Degree 131 trace | 566.30× | 608.63× |
| Degree 131 `pointFromX`, invalid abscissa | 5.26× | 4.43× |
| Degree 131 `pointFromX`, valid abscissa | 2.94× | 1.87× |

The paired benchmark used 64 trace inputs per degree, 24 abscissae of each
point-recovery outcome, nine alternating matched rounds, eight trace repeats
and two point-recovery repeats per round. Both sides used the same Euclid
inverse in point recovery to isolate the trace change. Output equality was
checked before and during timing. Run B's valid-point ratio varied from A,
so that stage should be read as a range, not a precise constant.

The first degree 131 trace call in seven fresh processes per side had median
**2.166 ms incumbent versus 0.0041 ms candidate**. The incumbent built the
exponent-1 Frobenius table; the canonical parity path built no table. This
first-call result is a trace-only measurement, not the cost of initializing a
complete IC run.

Exact comparison covered **4,639** trace and point outputs on Python 3.9
and 3.13. It included every 11-bit raw input at degree 5, 1,024 canonical
degree 9 and 131 inputs each, random noncanonical high-bit inputs, selected
negative values, and point recovery. The 14 Python 3.9 artifact replay tests
and three solver-independent local IC tests passed. All five parent archive
verifiers passed locally after this change. The curve-squaring archive
verifier now compares its frozen field module against the live one excluding
`trace`, which that experiment overrides for both sides of its benchmark.

This is an Apple Silicon CPU Python path; it does not use Metal. Complete
verified IC and DLP speedup remains **unknown** because the SAT-backed full
runner was unavailable locally and no calibrated recovered-log comparison
was measured. Stage timings do not substitute for the required phase total.
