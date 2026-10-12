# Q1488: first-pair restarts yield nine distinct N83 S3 pairs at about 2^16.5 calls each

Stopping each frozen leaf-polarity restart at its **first distinct
complete pair** measures the useful S3 root opportunity directly.
All nine phases reached nine different pair-1 assignments on each of
two ordinary N83 public points. Five pairs had two exact S3 middle
roots and four were rootless. Median work to the first pair was
**95,480 combined CNF/XOR calls (2^16.543)** on the selected point and
**97,804 calls (2^16.578)** on the holdout point.

| Point | Nine first pairs: combined calls | Median per first pair | Nine old 32,768-branch runs: combined calls | Old / first-pair work |
| --- | ---: | ---: | ---: | ---: |
| Selected, workload 2eb250a29072 | 880,988 | 95,480 | 180,093,147 | 204.4 |
| Holdout, workload 394256b9f901 | 900,735 | 97,804 | 178,297,066 | 197.9 |

The old matched-checkpoint runs spent nearly all their calls revisiting
their first pair. The new stop rule avoids that repeated work and gives
one distinct pair per restart in this frozen schedule. The nine pairs
and root outcomes are identical across the two public points, so this
part of the search is target independent for these inputs. The five
two-root and four rootless outcomes are observations from nine chosen
phases; they are not a statistical estimate of natural relation yield.

| Phase | Selected branch / calls | Holdout branch / calls | Exact S3 roots |
| ---: | ---: | ---: | ---: |
| 0 | 332 / 121,082 | 332 / 122,237 | 2 |
| 1 | 38 / 94,980 | 38 / 97,304 | 2 |
| 2 | 39 / 95,480 | 39 / 97,804 | 2 |
| 3 | 49 / 94,006 | 49 / 96,330 | 0 |
| 4 | 47 / 95,662 | 47 / 97,986 | 0 |
| 5 | 39 / 94,484 | 39 / 96,808 | 2 |
| 6 | 39 / 95,480 | 39 / 97,804 | 0 |
| 7 | 44 / 94,328 | 44 / 96,652 | 0 |
| 8 | 42 / 95,486 | 42 / 97,810 | 2 |

## Method and verification

The curve is EC1N83Ckb1h876c2921cb64, with actual usable
normal-basis weight-five factor base B=30,977,592, signed-Frobenius
folded K=186,612 columns, PDP4sat, and isogeny: "none". Q1488 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) fixes the two ordinary points, nine
Q1481 phase masks, resource caps, and the first-pair stop rule.
The [freeze](freeze.json) binds the Q1481 source and inputs, all mask
definitions, and the earlier 32,768-branch receipts.

The [instrumentation](first_pair.py) records the branch number and
exact CNF/XOR counters when the first complete distinct pair is
captured, then the driver terminates that attempt. It changes no
solver decisions before the marker. All 18 attempts have status
FIRST_PAIR_TERMINATED. The [validator](validate.py) reconstructs the
C patch, checks binary, input, log, and run hashes, verifies that
each pair matches the earlier Q1481 prefix, and independently replays
its exact S3 roots. Exact root queries consumed 794 CountedOnb public
field entries for the nine pairs on each point, reported separately
from CNF/XOR calls. Host wall and CPU timings are exploratory because
there is no isolation receipt.

## Next gate and challenge distance

This reduces measured **distinct-pair sampling** work by about 200
times relative to running every restart to the old checkpoint. It
does not yet measure a complete four-point decomposition or a useful
relation. The next experiment should generate a larger frozen mask
family, stop at the first pair, measure uniqueness and exact root
outcomes with uncertainty, then use each two-root pair to condition
the remaining four-point equations. Charge that continuation and
all failed attempts on the same ordinary target.

Until a complete ordinary relation and rank contribution are measured,
the fully charged N131 one-target 2^x estimate and gap to 2^61
remain null. The separate Q1462 conditional weight-seven pair-index
model remains 2^86.1847 counted pair additions, 25.1847 bits above
an abstract 2^61 pair-addition cap in that different unit.

    env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_first_pair_restart/validate.py
