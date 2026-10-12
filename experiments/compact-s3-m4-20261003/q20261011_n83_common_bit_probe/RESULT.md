# Q1485: 49 exact middle-bit implications are available at every recognized pair

The two exact S3 middle roots agree on 49 of 83 coordinate bits. At the
matched 32,768-left-branch checkpoint on each of two frozen ordinary N83
points, **all 49 common bits are undefined** at every one of 32,720
recognized leaf-pair states. These bits can be assigned without choosing
between the two roots. Q1485 only counts them; its CNF/XOR call counts
match Q1484 exactly.

| Workload | Q1484 calls | Q1485 calls | Recognized states | States with unset common bits | Min / max unset common bits |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2eb250a29072` | 16,099,925 | 16,099,925 | 32,720 | 32,720 | 49 / 49 |
| `394256b9f901` | 16,102,249 | 16,102,249 | 32,720 | 32,720 | 49 / 49 |

## Method and accounting

The curve is `EC1N83Ckb1h876c2921cb64`, with actual usable
normal-basis weight-five factor base `B=30,977,592`, signed-Frobenius
folded `K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1485 is a
point-decomposition stage proposal with null candidate and run IDs.
The [protocol](protocol.json) and [freeze](freeze.json) bind the Q1484
binary source, both ordinary public points, the exact root pair, phase-4
polarity, and resource caps. The [patch](build.py) counts common-root
bits still undefined when the complete leaf pair is recognized. It
changes no solver decisions.

Both ordinary attempts have status `CHECKPOINT_TERMINATED` and add
15.526 exploratory solver wall seconds and 1.003 child user CPU seconds
to their respective point ledgers. Host isolation was not recorded, so
the exact counters are the paired diagnostic. [Validation](validate.py)
reconstructs the patch, checks the source, binary, input, run, and
analysis hashes, and verifies matching paired CNF/XOR counts.

## Next gate and challenge distance

The next controlled change is to enqueue those 49 signed literals into
both WDSat propagation stacks when this complete leaf pair appears,
while preserving the exact root support check. Measure new branch,
conflict, and distinct-pair counts on the same two public points; replay
any model independently. Dynamic root memoization should follow only if
the static implication changes the search.

No ordinary verified relation or rank contribution has yet been
measured for this bounded prefix, so complete N131 one-target `2^x`
work and the gap to `2^61` remain null. The separate Q1462 conditional
weight-seven pair-index model remains `2^86.1847` counted pair additions,
25.1847 bits above an abstract `2^61` pair-addition cap in that distinct
unit.

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_common_bit_probe/validate.py
```
