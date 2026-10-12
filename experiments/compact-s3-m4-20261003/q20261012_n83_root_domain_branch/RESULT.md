# Q1489: early S3 root-bit branching saves 0.804% of N83 solver calls

The first coordinate bit that distinguishes the two exact S3 middle
roots was moved immediately after the four leaf-coordinate rows in
WDSat's branch order. With all other solver decisions unchanged,
combined CNF/XOR calls to the matched 32,768-left-branch checkpoint
fell by **0.804%** on each of two frozen ordinary N83 public points.
Each run still exposed one distinct pair with two exact roots.

| Workload | Q1485 original order | Q1489 early bit, order only | Q1489 early bit plus root-domain forcing |
| --- | ---: | ---: | ---: |
| 2eb250a29072 | 16,099,925 | 15,970,529 | 26,701,611 |
| 394256b9f901 | 16,102,249 | 15,972,839 | 25,352,677 |

The root-domain variant selected one of the two verified roots after
the distinguishing bit was assigned and propagated its remaining
undefined middle bits through native CNF/XOR inference. It forced 43
literals on each point, with no failed recursive implication. Its
calls rose by 67.2% and 58.7% relative to the order-only variant,
without increasing pair diversity at this bound. The order-only
variant is the useful setting from this comparison.

## Exact method and verification

The curve is EC1N83Ckb1h876c2921cb64, with actual usable
normal-basis weight-five factor base B=30,977,592, signed-Frobenius
folded K=186,612 columns, PDP4sat, and isogeny: "none". Q1489 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) fixes both public points, phase-4 leaf
polarity, 32,768-branch checkpoint, and both variants.
The [freeze](freeze.json) binds the exact two-root pair, source and
input hashes, and the 335-entry priority prefix. Its distinguishing
middle bit is coordinate 6, WDSat variable 423.

The [patch](build.py) inserts all four leaf rows, the root
discriminator, and the two selectors before the remaining variables.
The optional domain rule applies only when all 166 bits of the
verified pair match, and its signed implications are necessary for
the selected exact S3 root. Existing rootless-pair and two-root
support checks remain active. [Validation](validate.py) reconstructs
the C patch, rechecks the exact roots through predecessor validation,
verifies source, binary, input, and run hashes, and audits the sampled
S3 roots on both points.

All four new ordinary attempts have status CHECKPOINT_TERMINATED and
add 38.110 exploratory solver wall seconds and 2.197 child user CPU
seconds to their respective point ledgers. Host isolation was not
recorded, so wall and CPU ratios are diagnostics; the exact paired
CNF/XOR counters support the stage comparison.

## Next gate and challenge distance

The two roots differ in 34 coordinate positions. A frozen
hyperparameter sweep should move each differing bit to the same early
branch slot, screen all 34 positions on the selected point, and
confirm the best few on the holdout point. It should count exact
pair diversity and root outcomes as well as CNF/XOR work. Forcing
the complete root after that early branch is not favored by these
two measurements.

An ordinary verified four-point relation and rank contribution are
still needed to fit complete N131 one-target 2^x work. That estimate
and gap to 2^61 remain null. The separate Q1462 conditional
weight-seven pair-index model remains 2^86.1847 counted pair
additions, 25.1847 bits above an abstract 2^61 pair-addition cap in
that different unit.

    env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_root_domain_branch/validate.py
