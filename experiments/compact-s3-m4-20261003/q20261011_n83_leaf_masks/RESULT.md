# Q1481: leaf-only polarity phase 4 exposes an exact rootless N83 pair

Compiling eight target-independent leaf-only first-branch masks into the
native-XOR WDSat binary repairs Q1480's selector-mask preflight failure.
All 18 ordinary N83 cells reached the same 32,768-left-branch checkpoint.
On **both** frozen public points, phases 3, 4, 6, and 7 expose one distinct
complete pair-1 leaf assignment whose exact S3 equation has **zero**
middle-coordinate roots. Phase 4 is the lowest-propagation-cost rootless
cell: **16,076,575** combined CNF/XOR calls on the selected point and
**16,078,899** on the holdout, versus 27,860,226 and 26,045,553 for phase
0. These are **42.3%** and **38.3%** fewer calls at the matched checkpoint.

| Phase | Selected: distinct / rootless | Selected combined calls | Holdout: distinct / rootless | Holdout combined calls |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 / 0 | 27,860,226 | 1 / 0 | 26,045,553 |
| 1 | 1 / 0 | 16,810,430 | 1 / 0 | 16,812,754 |
| 2 | 1 / 0 | **14,163,659** | 1 / 0 | **14,165,983** |
| 3 | 1 / 1 | 24,093,898 | 1 / 1 | 24,096,222 |
| **4** | **1 / 1** | **16,076,575** | **1 / 1** | **16,078,899** |
| 5 | 1 / 0 | 20,723,647 | 1 / 0 | 20,725,971 |
| 6 | 1 / 1 | 19,649,636 | 1 / 1 | 19,651,960 |
| 7 | 1 / 1 | 24,509,271 | 1 / 1 | 24,511,595 |
| 8 | 1 / 0 | 16,205,805 | 1 / 0 | 16,208,129 |

Each row has status `CHECKPOINT_TERMINATED`; the [raw receipts](runs) retain
the separate CNF and XOR counters, branch and root-ready checkpoints,
first distinct leaf-pair bitstring, CPU/wall caps, and hashes. The combined
count is a named internal diagnostic, not calibrated field operations.
For phase 4 it is `2^23.938` calls on either point. An exact rootless query
uses 21 counted `CountedOnb` public field entries, including coordinate
conversion and the trace test. The phase-4 rootless leaf bitstring is
identical on the two points. All nine phases still expose only one distinct
pair in this prefix, so the masks change the first pair and its algebraic
outcome without improving pair diversity.

## Frozen method and checks

The curve is `EC1N83Ckb1h876c2921cb64`, with actual usable normal-basis
weight-five factor base `B=30,977,592`, signed-Frobenius folded
`K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1481 remains a
stage proposal with null candidate and run IDs. The [protocol](protocol.json)
sets the two ordinary points, same branch order, checkpoint, cap, and
pointwise score. [Mask generation](mask_schedule.py) fixes seeds
148101–148108 and only variables 2–333, excluding selectors and
midpoints. The exact lists, source, inputs, and prior Q1479 binary are
bound in the [freeze](freeze.json). The [build](build.py) inserts those
masks after the old selector policy with `Q1472_PHASE_INDEX=0`.

[Validation](validate.py) reconstructs the source patch, checks all 18
binary/input/log identities and mask markers, independently checks the S3
root counts and returned roots, and reproduces both pointwise rankings.
Phase 0 reproduces Q1479's branch-ready and propagation checkpoints on
each point exactly. The 18 new attempts add **106.621 exploratory solver
wall seconds** and **10.204 child user CPU seconds** across the two
targets; each attempt is charged to its own public point. Host timing has
no isolation receipt. The preceding Q1480 preflight failure remains
[preserved](../q20261011_n83_leaf_polarity_screen/PREFLIGHT_RESULT.md)
as an implementation failure rather than an algorithmic result.

## Challenge distance and next solver change

Phase 4 offers a sound exact conflict: its complete leaf-pair assignment
has no S3 middle root, so that assignment can be rejected wherever it
appears. Q1481 measures the opportunity before rejection; it does not yet
measure whether a native-XOR search with that rejection explores new pairs
or returns a relation. Natural relation yield, rank novelty, complete
N83 decomposition cost, and normalized N131 one-target work remain null.
The separate Q1462 conditional weight-seven full pair-index model is
`2^86.1847` counted pair additions, 25.1847 bits above an abstract
`2^61` pair-addition cap in its different unit.

The next controlled experiment should add a verified nogood for the
phase-4 rootless pair to the same native-XOR binary, hold both public
points and the phase-4 mask fixed, and compare at a matched branch and
propagation-call budget. Count newly reached distinct leaf pairs and
their exact roots, then independently replay any returned group relation.

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_leaf_masks/validate.py
```
