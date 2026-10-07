# Multiplication/squaring-aware selective atlas: design screen

`WEIGHTED_MIXED_SCREEN.md` and `weighted_mixed_screen.py` were frozen in
`c3b1a1ac` before the original 64-case design fixture was screened.
The scalar weights below are **hypothetical**. They are not measured
field-kernel calibration and do not support a CPU performance claim.

| Assumed `S/M` | Equal-weight stream, rescored | Weight-specific stream | Saving | Changed streams |
| ---: | ---: | ---: | ---: | ---: |
| 0.50 | 72,476 `M`-equivalent units | 72,465 | 11 (0.0152%) | 11/64 |
| 0.75 | 79,887 | 79,885.75 | 1.25 (0.00156%) | 4/64 |
| 1.00 | 87,298 | 87,298 | 0 | 0/64 |

At `S/M=1`, the new vector-cost implementation reproduced every
saved selected digit hash and per-case `M+S` source count from the
original selective screen. It separately recounted each chosen
stream's `(M,S)` vector and reconstructed its exact short Eisenstein
representative. At `S/M=0.50`, the chosen streams total **57,617 M +
29,696 S** across the panel; at `S/M=0.75`, **57,637 M + 29,665 S**;
and at equal weights, **57,654 M + 29,644 S**. The raw per-case
vectors, weights, choices, and source hashes are in
`weighted-mixed-design-result.json` (SHA-256
`069c9fdcda8b2f2720ceac5859908fe950bea5cf7ceb021c1fa5576aeb59dc34`).

The screen gives little reason to build a weight-specific native
selector: even an aggressive assumed squaring discount changes the
source objective by only 0.0152% on design data, before selector CPU
work. No fresh holdout, independent point replay of the changed
streams, or isolated CPU timing was run. The next algorithmic search
should target point arithmetic or a more different chain rather than
this recoder reweighting. Academic novelty remains unproved.
