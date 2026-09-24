# Result: density-aware ONB coordinate packing

The accepted field source is SHA-256
`148d795b6216254813e7dbe189e1290ae286dd9edb2b0a3c3fe2870788c81918`.
For at most 12 set coordinate bits, `Onb.fromCoords` creates only the needed
symmetric bit pairs. Dense inputs reverse bits within bytes and combine the
result with the original low coordinate half. Both paths mask to the original
`m` input bits.

| Warm field stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 random `fromCoords` | 1.09× | 1.19× |
| Degree 9 random `fromCoords` | 1.19× | 1.07× |
| Degree 131 random `fromCoords` | 30.53× | 39.86× |
| Degree 131 one-bit coordinate | 17.62× | 19.40× |
| Degree 131 two-bit coordinate | 12.82× | 13.65× |
| Degree 131 dense coordinate | 52.65× | 50.36× |
| Sparse `pointFromX(fromCoords(...))` | 1.093× | 1.071× |

`benchmark.py` used 64 identical seeded values per case, 9 alternating
paired rounds, and 16 repeats per round; field ratios divide the recorded
median times. The containing point-build result used 64 identical two-bit
coordinate inputs, 11 matched rounds, and 32 repeats per round; its ratio is
the median of matched old/new round ratios. The same curve, Euclid inverse,
and trace code ran on both sides, and all point outputs matched exactly.
The containing-stage gain is smaller because point recovery does much more
than coordinate packing.

`verify.py` matched **6,866** original outputs across ten valid ONB degrees,
including exhaustive degree-5 coordinates, high bits, negative values, and
random values around byte-alignment boundaries. `Onb.selfTest` passed at
degrees 5, 9, and 131. Five local IC tests independent of CryptoMiniSat passed
with the candidate loaded first.

The first set-bit-only candidate improved sparse inputs but regressed dense
degree-131 packing to about 0.55×. The byte-reversal route cleared the frozen
dense gate. The first containing-stage runs varied from 1.04× to 0.83×; a
frozen longer-round repeat produced the 1.093× and 1.071× diagnostics above.
All versions and raw measurements are retained.

These are local Apple Silicon CPU arithmetic-stage results. This Python ONB
path does not use Metal. A complete index-calculus or DLP speedup remains
**unknown** because the local SAT solver dependency is unavailable and there
is no calibrated common operation-unit recovered-log comparison.
