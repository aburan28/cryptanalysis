# Result: direct ONB coordinate extraction

The accepted field source is SHA-256
`0fe128a2aa80b9601b307be0f3b1e94f0206944b5f7cf3e7b9782583b1345e39`.
The only source change is `Onb.toCoords`: normalization remains identical,
and `(u >> 1) & ((1 << m) - 1)` selects exactly the bits previously read by
the loop.

| Warm stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| `toCoords`, degree 5 random | 3.34× | 3.39× |
| `toCoords`, degree 9 random | 4.74× | 4.62× |
| `toCoords`, degree 131 random | 57.05× | 81.90× |
| `toCoords`, degree 131 sparse | 28.95× | 29.30× |
| Audit-style trace, degree 131 | 61.10× | 71.29× |
| `Curve.pointFromX`, degree 131 | 1.048× | 1.040× |

The extraction benchmark used 64 identical seeded inputs per case, 9
alternating paired rounds, and 32 repeats per round. Its ratios divide the
recorded median times. The containing point-recovery benchmark used 48
identical seeded abscissae, 11 matched rounds, and 16 repeats per round; its
ratio is the median of the matched old/new round ratios. Exact point outputs
matched. The point-recovery gain is much smaller because it also performs
inversion, Frobenius, multiplication, and a curve check.

`verify.py` matched **7,055** original coordinate outputs, including every
degree-5 raw bit pattern, random raw degree-9/131 patterns, canonical
coordinates, high bits, and negative inputs. `Onb.selfTest` passed at degrees
5, 9, and 131. Five local IC tests that do not require CryptoMiniSat passed
with the candidate field loaded first.

These are local Apple Silicon CPU arithmetic-stage results. The Python ONB
path does not call Metal. A complete index-calculus or DLP speedup remains
**unknown** because this environment lacks the local SAT solver dependency
and has no calibrated common operation-unit recovery comparison.
