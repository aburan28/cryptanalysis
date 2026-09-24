# Result: direct ONB coordinate extraction

The accepted field source is SHA-256
`eff1274128554c4b81dc861440497ad809eb9aa2e81938ae0c4933eadaffe6be`.
The only source change is `Onb.toCoords`: normalization remains identical,
and `(u >> 1) & ((1 << m) - 1)` selects exactly the bits previously read by
the loop.

| Warm stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| `toCoords`, degree 5 random | 3.39× | 3.37× |
| `toCoords`, degree 9 random | 4.66× | 4.74× |
| `toCoords`, degree 131 random | 76.92× | 90.08× |
| `toCoords`, degree 131 sparse | 29.21× | 30.50× |
| Audit-style trace, degree 131 | 74.56× | 28.27× |
| `Curve.pointFromX`, degree 131 | 1.160× | 1.017× |

The extraction benchmark used 64 identical seeded inputs per case, 9
alternating paired rounds, and 32 repeats per round. Its ratios divide the
recorded median times. The containing point-recovery benchmark used 48
identical seeded abscissae, 11 matched rounds, and 16 repeats per round; its
ratio is the median of the matched old/new round ratios. The second containing
run is near parity and the audit-style trace timing varies substantially; raw
rounds are retained. Exact point outputs matched. The point-recovery gain is much smaller because it also performs
inversion, Frobenius, multiplication, and a curve check.

`verify.py` matched **7,055** original coordinate outputs, including every
degree-5 raw bit pattern, random raw degree-9/131 patterns, canonical
coordinates, high bits, and negative inputs. `Onb.selfTest` passed at degrees
5, 9, and 131. Five local IC tests that do not require CryptoMiniSat passed
with the candidate field loaded first. The exact comparison also passed on
Python 3.9, along with its 14 artifact replay tests.

These are local Apple Silicon CPU arithmetic-stage results. The Python ONB
path does not call Metal. A complete index-calculus or DLP speedup remains
**unknown** because this environment lacks the local SAT solver dependency
and has no calibrated common operation-unit recovery comparison.
