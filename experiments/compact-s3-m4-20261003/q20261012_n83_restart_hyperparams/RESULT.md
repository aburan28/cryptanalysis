# Q1497: 208-flip restarts give the lowest cost per distinct usable first pair

The frozen N83 selected-point sweep measured eight fresh leaf-polarity masks
at each of four flip counts, stopping WDSat at its first complete S3 pair.
Every one of the 32 ordinary-query runs reached that boundary within the
declared 45-second CPU and 90-second wall caps. Q1495's exact predicate
classified the resulting two x coordinates against the B=30,977,592
point, K=186,612 column base.

| Flipped leaf variables | Runs | Distinct first pairs | Distinct usable pairs | Charged CNF/XOR calls | Calls per distinct usable pair |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 208 | 8 | 8 | 4 | 769,426 | **192,357 = 2^17.553** |
| 249 | 8 | 8 | 4 | 776,480 | 194,120 = 2^17.566 |
| 290 | 8 | 6 | 3 | 784,046 | 261,349 = 2^17.996 |
| 331 | 8 | 1 | 1 | 795,456 | 795,456 = 2^19.601 |

The original preregistered analyzer selected 331 flips by calls per accepted
attempt, but all eight selected and all eight holdout runs at that setting
repeated the same pair. The [versioned distinct-pair analysis](distinct_analysis.json)
preserves this result and selects 208 flips for novel usable output. The
earlier Q1491 selected 249-flip panel cost 778,598 calls for three distinct
usable pairs, or 259,533 calls per pair. Q1497's 208-flip panel is 0.432
bits lower on the same selected point. With only eight masks per setting,
the usable fractions have wide uncertainty: the 95% Wilson interval for
four accepted masks in eight is 0.215–0.785, overlapping the prior 249-flip
panel's three in eight interval of 0.137–0.694. This is an observed panel
improvement and a holdout choice, not a stable rate estimate.

The [protocol](protocol.json) and [freeze](freeze.json) bind the curve,
factor base, two input points, Q1491 solver source, fresh masks, build, caps,
and exact membership code. [Per-run receipts](runs) preserve first-pair
bits, CNF/XOR counters, status, exploratory wall/CPU, and source/input
hashes. This is a `PDP4sat` stage proposal with null candidate/run IDs and
`isogeny: "none"`. Complete relation yield, rank, matrix solving, target
descent, and degree-131 complete-solve work remain to be measured.

Q1498 replays the duplicate-aware 208-flip choice on the frozen ordinary
holdout point with the same masks and binary.
