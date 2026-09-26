# Result: density-aware ONB coordinate packing

The accepted field source is SHA-256
`191584f34e0092922cf8747d075a0791df702b6153923285b48736d96b0c6c03`.
For at most 12 set coordinate bits, `Onb.fromCoords` creates only the needed
symmetric bit pairs. Dense inputs reverse bits within bytes and combine the
result with the original low coordinate half. Both paths mask to the original
`m` input bits. The density check uses the inherited Python 3.9-compatible
bit-count binding, and fields of degree at most 12 take the sparse path directly.

| Warm field stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 random `fromCoords` | 1.16× | 1.15× |
| Degree 9 random `fromCoords` | 1.21× | 1.20× |
| Degree 131 random `fromCoords` | 30.16× | 29.03× |
| Degree 131 one-bit coordinate | 14.41× | 14.60× |
| Degree 131 two-bit coordinate | 10.02× | 9.94× |
| Degree 131 dense coordinate | 56.14× | 71.79× |
| Sparse `pointFromX(fromCoords(...))` | 1.147× | 1.084× |

`benchmark.py` used 64 identical seeded values per case, 9 alternating
paired rounds, and 16 repeats per round; field ratios divide the recorded
median times. The containing point-build result used 64 identical two-bit
coordinate inputs, 11 matched rounds, and 32 repeats per round; its ratio is
the median of matched old/new round ratios. The same curve, Euclid inverse,
and trace code ran on both sides, and all point outputs matched exactly.
The containing-stage gain is smaller because point recovery does much more
than coordinate packing.

`verify_v3.py` matched **6,866** original outputs across ten valid ONB degrees,
including exhaustive degree-5 coordinates, high bits, negative values, and
random values around byte-alignment boundaries. `Onb.selfTest` passed at
degrees 5, 9, and 131. Five local IC tests independent of CryptoMiniSat passed
with the candidate loaded first. Exact output checks passed under Python 3.9
and 3.13, and the 14 Python 3.9 artifact replay tests passed locally.

The first set-bit-only candidate improved sparse inputs but regressed dense
degree-131 packing to about 0.55×. The byte-reversal route cleared the frozen
dense gate, but initially used `int.bit_count`, which failed the Python 3.9
artifact replay. The accepted version uses the inherited compatibility binding.
The first containing-stage runs varied from 1.04× to 0.83×; frozen longer
rounds and the corrected parent produced the refreshed diagnostics above.
All versions and raw measurements are retained.

These are local Apple Silicon CPU arithmetic-stage results. This Python ONB
path does not use Metal. A complete index-calculus or DLP speedup remains
**unknown** because the local SAT solver dependency is unavailable and there
is no calibrated common operation-unit recovered-log comparison.
