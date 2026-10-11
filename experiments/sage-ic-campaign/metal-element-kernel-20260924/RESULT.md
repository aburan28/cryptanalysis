# Result: hold the Metal per-element kernel

The measured operation includes Sage point packing, mapping, point
construction, and batch splitting on a degree-131 Koblitz curve with
Frobenius power 65. Each arm ran eight times in rotating, reversing order
inside a fresh Sage process. All outputs matched native Sage. Values below
are full warm operation medians in ms; verification and cleanup were recorded
separately.

| Candidate / run | Points | Current Metal | Element Metal | Element / current | Batched CPU | Native Sage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dynamic array, pilot 1 | 1,024 | 0.500 | 0.539 | 1.076x | 0.389 | 6.673 |
| Dynamic array, pilot 1 | 4,096 | 1.892 | 2.135 | 1.129x | 1.576 | 27.354 |
| Fixed accumulators, pilot 2 | 1,024 | 0.883 | 0.888 | 1.006x | 0.371 | 6.613 |
| Fixed accumulators, pilot 2 | 4,096 | 2.169 | 1.788 | 0.824x | 1.509 | 26.552 |
| Fixed accumulators, confirm | 1,024 | 0.509 | 0.483 | 0.948x | 0.356 | 6.574 |
| Fixed accumulators, confirm | 4,096 | 1.749 | 1.813 | 1.037x | 1.584 | 26.232 |
| Fixed accumulators, confirm | 4,096 | 1.895 | 1.905 | 1.005x | 1.645 | 27.404 |
| Fixed accumulators, confirm | 16,384 | 5.370 | 5.910 | 1.100x | 5.349 | 110.738 |

The sole large pilot gain reversed on both independent 4,096-point seeds.
The 16,384-point confirmation was 10% slower. The static candidate also
remained slower than batched CPU in every measured cell. Process peak RSS was
268–295 MiB, below the declared 512 MiB resource budget. Plan construction
and shader compilation were recorded but are too variable in these mixed-arm
processes to support a cold speedup claim; the static shader ranged from
13–141 ms setup in the second pilot.

**Decision:** keep the existing word kernel. Next test the table layout and
coalescing hypothesis with the same exact output and full-call gates. There
is no complete IC or verified DLP result in these measurements.
