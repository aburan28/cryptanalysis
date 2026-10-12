# Q1490: 34 root-bit positions produce one N83 pair; bit 80 saves 92 calls

All 34 coordinate positions that distinguish the two exact S3 middle
roots were tested in the same early WDSat branch slot on one frozen
ordinary N83 point. Every run reached the 32,768-left-branch checkpoint
and exposed **one distinct pair with two exact roots**. The lowest
combined CNF/XOR count was 15,970,437 for bit 80, only 92 calls below
the bit-6 setting from Q1489. Twenty positions tied at 15,970,529
calls; the highest count was 17,473,717 at bit 71.

| Position | Selected calls | Holdout calls | Distinct pairs per point |
| ---: | ---: | ---: | ---: |
| 80, lowest selected | 15,970,437 | 15,972,761 | 1 |
| 6, predecessor | 15,970,529 | 15,972,839 | 1 |
| 7, tied holdout | 15,970,529 | 15,972,839 | 1 |
| 71, highest selected | 17,473,717 | not promoted | 1 |

The frozen ranking promoted bits 80, 6, and 7 to the holdout point.
Bit 80 again used the fewest calls, saving 78 relative to bit 6.
Compared with the original Q1485 branch order, bit 80 uses **0.804%
fewer** combined calls on both points. This is a bounded stage
improvement; no tested position increased pair diversity.

## Method and verification

The curve is EC1N83Ckb1h876c2921cb64, with actual usable
normal-basis weight-five factor base B=30,977,592, signed-Frobenius
folded K=186,612 columns, PDP4sat, and isogeny: "none". Q1490 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) fixes the selected and holdout points,
phase-4 polarity, resource caps, and holdout ranking. The
[freeze](freeze.json) binds the 34 exact differing positions, source,
input, and predecessor receipts before compilation or search.

One [binary and driver](sweep.py) validates a differing-bit index,
places its middle-coordinate variable after the four leaf rows, and
keeps exact root-domain forcing disabled. Each run retains its mask
marker, raw log, and resource receipt. [Validation](validate.py)
reconstructs the C patch, checks all 37 source, binary, input, log,
and run hashes, recomputes the holdout ranking, and verifies every
sampled S3 root pair. All 37 attempts have status
CHECKPOINT_TERMINATED. Together they add 276.766 exploratory solver
wall seconds and 17.580 child user CPU seconds to their point ledgers.
Host isolation was not recorded, so wall and CPU ratios remain
diagnostics.

## Next gate and challenge distance

Changing this one branch position has exhausted its useful range at
the checkpoint: the 34-position sweep found no pair-diversity gain.
The Q1488 first-pair restart schedule is a better source of distinct
pairs. The next measurement should pair its first-pair work with an
N53 run under the same stop boundary and then charge the exact
target-dependent continuation from each two-root pair toward a full
four-point decomposition. Root checks alone are not relations.

A complete ordinary relation, rank contribution, target descent,
and final linear algebra are still needed to fit fully charged N131
one-target 2^x work; that estimate and its gap to 2^61 remain null.
The separate Q1462 conditional weight-seven pair-index model remains
2^86.1847 counted pair additions, 25.1847 bits above an abstract
2^61 pair-addition cap in that different unit.

    env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_discriminator_sweep/validate.py
