# Q1487: eight common-bit subsets do not improve N83 pair exposure

A frozen eight-mask sweep restricted exact S3 common-root propagation to
one, four, eight, or sixteen selected middle bits. Every mask reached
the matched 32,768-left-branch checkpoint on the selected ordinary N83
point. Each still exposed one distinct leaf pair with two exact roots.
The lowest combined CNF/XOR count was 16,229,163 calls for last1,
**0.803% above** the unforced Q1485 count of 16,099,925.

| Selected mask | Bits forced | CNF+XOR calls | Distinct pairs |
| --- | ---: | ---: | ---: |
| first1 | 1 | 16,229,255 | 1 |
| middle1 | 1 | 16,229,255 | 1 |
| last1 | 1 | 16,229,163 | 1 |
| first4 | 4 | 16,358,937 | 1 |
| spread4 | 4 | 16,628,837 | 1 |
| spread8 | 8 | 17,135,293 | 1 |
| spread16 | 16 | 19,795,169 | 1 |
| last8 | 8 | 21,386,589 | 1 |

The frozen ranking rule advanced last1 and first1 to the holdout public
point. Both again exposed one two-root pair. Holdout calls were
16,231,487 and 16,231,565 respectively, **0.803% above** the unforced
Q1485 holdout count of 16,102,249. The all-49 Q1486 setting is a
separate predecessor measurement: 23,392,563 selected and 22,466,379
holdout calls. All ten new ordinary attempts have status
CHECKPOINT_TERMINATED. Every sampled pair was replayed through the
exact S3 root oracle; each sample had two roots.

## Method and accounting

The curve is EC1N83Ckb1h876c2921cb64, with actual usable normal-basis
weight-five factor base B=30,977,592, signed-Frobenius folded
K=186,612 columns, PDP4sat, and isogeny: "none". Q1487 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) freezes the eight bit-rank rules,
selected/holdout workloads, phase-4 polarity, resource caps, and
holdout selection rule. The [freeze](freeze.json) lists every exact
83-bit mask and its coordinate positions before compilation or search.
One [binary and driver](sweep.py) handles every variant; only the
validated Q1487_MASK value changes.

Each selected mask picks positions from the 49 bits shared by both
exact S3 roots, so every forced literal is necessary for that complete
leaf pair. The existing rootless and two-root support checks remain.
[Validation](validate.py) reconstructs the C patch, checks all ten
input, source, binary, log, and run hashes, recomputes the holdout
ranking, and verifies the exact-root samples. The ten attempts add
50.533 exploratory solver wall seconds and 5.209 child user CPU seconds
to their point ledgers. Host isolation was not recorded, so the paired
exact CNF/XOR counters are the comparison.

## Next gate and challenge distance

Exact implications introduced only after a complete leaf pair is
assigned have not increased distinct-pair yield at this checkpoint,
even when 49 bits were available. The next useful solver experiment
should change how often *new* leaf pairs are reached: instrument the
first variable or constraint that keeps the search revisiting this
pair, then sweep that branch-order decision on selected and holdout
points. Charge any exact-root lookup and every ordinary failed
attempt. An ordinary verified relation and rank contribution are
still needed to fit complete N131 one-target 2^x work; that estimate
and gap to 2^61 remain null. The separate Q1462 conditional
weight-seven pair-index model remains 2^86.1847 counted pair
additions, 25.1847 bits above an abstract 2^61 pair-addition cap in
that distinct unit.

    env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_common_subset_sweep/validate.py
