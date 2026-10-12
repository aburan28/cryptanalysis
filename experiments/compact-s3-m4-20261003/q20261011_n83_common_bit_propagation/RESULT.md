# Q1486: forcing all 49 common S3 bits increases N83 propagation work

Both exact S3 middle roots agree on 49 coordinate bits. Native WDSat
propagation was extended to assign those mandatory literals when their
complete leaf pair appears. On two frozen ordinary N83 public points, it
assigned all 49 bits once per point. At the matched 32,768-left-branch
checkpoint, combined CNF/XOR calls increased **45.3%** and **39.5%**
relative to Q1485, while each search still exposed one distinct pair.

| Workload | Q1485 CNF+XOR calls | Q1486 calls | Ratio | Forced literals | Distinct pairs / exact roots |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2eb250a29072 | 16,099,925 | 23,392,563 | 1.453 | 49 | 1 / 2 |
| 394256b9f901 | 16,102,249 | 22,466,379 | 1.395 | 49 | 1 / 2 |

No recursive implication failed. The maximum recursive depth was 49.
The one sampled pair on each point has two independently replayed S3
middle roots; the exact root replay used 142 CountedOnb public field
entries per point. The 49 forced literals, 13,924,949 separate
implication bit tests, field entries, and CNF/XOR calls have distinct
operation boundaries and are not added into a single uncalibrated cost.

## Method and verification

The curve is EC1N83Ckb1h876c2921cb64, with actual usable
normal-basis weight-five factor base B=30,977,592, signed-Frobenius
folded K=186,612 columns, PDP4sat, and isogeny: "none". Q1486 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) and [freeze](freeze.json) bind the Q1485
source, both public points, the two exact roots, phase-4 polarity,
branch cap, and resource caps.

The [patch](build.py) recognizes the complete 166-bit leaf pair after
a positive-bit prefilter. It finds the first still-undefined
middle-coordinate bit on which both roots agree and recursively calls
the existing native CNF/XOR inference path with that signed literal.
It repeats until no common bit remains. Existing Q1482 rootless and
Q1483 two-root support checks remain active. The solver's ordinary
backtracking reverts these implications with its branch assignments.

Both attempts have status CHECKPOINT_TERMINATED; together they add
14.999 exploratory solver wall seconds and 1.249 child user CPU seconds
to their respective point ledgers. Host isolation was not recorded, so
wall and CPU times are diagnostics. [Validation](validate.py)
reconstructs the source patch, verifies binary, input, log, run, and
analysis hashes, and replays the sampled exact roots.

## Next gate and challenge distance

The all-49 setting adds work without increasing pair diversity at this
checkpoint. A bounded hyperparameter search should choose subsets of
common bits by their CNF/XOR incidence or propagation leverage, screen
them on the selected N83 point, and confirm the best few on the frozen
holdout point. Record every failed or capped variant, the exact subset,
and all ordinary attempts. A smaller subset could improve the search
even though the all-bit setting does not.

An ordinary verified relation and rank contribution are still needed
to fit complete N131 one-target 2^x work. That estimate and its gap
to 2^61 remain null. The separate Q1462 conditional weight-seven
pair-index model remains 2^86.1847 counted pair additions, 25.1847
bits above an abstract 2^61 pair-addition cap in that distinct unit.

    env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_common_bit_propagation/validate.py
