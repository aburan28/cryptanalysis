# Q1483: exact two-root support leaves the N83 search unchanged

An exact compatibility filter for the two S3 middle roots of the Q1482
leaf pair was added to native WDSat propagation. On each of two frozen
ordinary N83 points, it checked the pair 32,720 times but found **zero**
partial middle assignments incompatible with both roots. At the common
32,768-left-branch checkpoint, the combined CNF/XOR call count and the
single distinct sampled leaf pair are exactly the same as Q1482.

| Workload | Q1482 CNF+XOR calls | Q1483 calls | Support checks | Pair matches | Support rejections | Separate bit tests |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2eb250a29072` | 16,099,925 | 16,099,925 | 32,767 | 32,720 | 0 | 13,906,147 |
| `394256b9f901` | 16,102,249 | 16,102,249 | 32,767 | 32,720 | 0 | 13,906,147 |

Both attempts have status `CHECKPOINT_TERMINATED`. The support checks add
work without eliminating a branch in this prefix. The two attempts add
10.264 exploratory solver wall seconds and 1.010 child user CPU seconds
to their respective point ledgers. The host has no isolation receipt, so
the wall measurements are diagnostics; the exact counters are the paired
comparison.

## Method and verification

The curve is `EC1N83Ckb1h876c2921cb64`, with actual usable
normal-basis weight-five factor base `B=30,977,592`, signed-Frobenius
folded `K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1483 is a
point-decomposition stage proposal with null candidate and run IDs. The
[protocol](protocol.json) freezes the two workloads, Q1481 phase-4
polarity, source parent, and branch and resource caps. The
[freeze](freeze.json) binds the complete 166-bit leaf pair, both exact
83-bit S3 middle roots, source hashes, and input hashes. The exact root
oracle and S3 evaluations are rechecked independently.

The [patch](build.py) recognizes the full leaf pair after a cheap
positive-bit prefilter. It rejects only if assigned middle-coordinate
bits disagree with **both** exact roots. This is a sound partial-support
test for that pair. The retained Q1482 rootless-pair nogood also remains
active. [Validation](validate.py) reconstructs the patched C source,
checks the binary and input receipts, replays root calculations, and
compares the two ordinary point logs with Q1482. The new pair has two
roots on both points; its sampled root query uses 142 counted
`CountedOnb` public field entries. Field entries, bit tests, and solver
calls have different boundaries and are reported separately.

## Next gate and challenge distance

The next measurement should count how often exactly one of the two roots
remains compatible, then test sound propagation of its unassigned middle
bits if that count is material. A dynamic version can memoize new leaf
pairs and their exact roots, charging the root lookup and every failed
search branch. An ordinary verified relation and rank contribution are
needed to fit complete N131 one-target work. Accordingly, the complete
N131 `2^x` estimate and gap to `2^61` remain null. The separate Q1462
conditional weight-seven pair-index model remains `2^86.1847` counted
pair additions, a 25.1847-bit gap to an abstract `2^61` pair-addition
cap in that distinct unit.

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_two_root_support/validate.py
```
