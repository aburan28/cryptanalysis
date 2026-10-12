# Q1482: an exact S3 nogood redirects the N83 search once

A mathematically verified rootless leaf-pair assignment was inserted as a
native-WDSat conflict on the Q1481 phase-4 path. It fired **once** on each
of two frozen ordinary N83 public points and redirected the search to a
different leaf pair with two exact S3 roots. At the common 32,768-left-
branch checkpoint, each patched search still saw **one distinct pair**.
The exact cut changes the path but does not improve distinct-pair yield
under this bound.

| Workload | Q1481 phase-4 CNF+XOR calls | Q1482 calls | Nogood rejections | Nogood bit tests | New distinct pairs / exact roots |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2eb250a29072` | 16,076,575 | 16,099,925 | 1 | 327,689 | 1 / 2 |
| `394256b9f901` | 16,078,899 | 16,102,249 | 1 | 327,689 | 1 / 2 |

The patched solver uses **0.145% more** combined CNF/XOR calls at this
checkpoint on either point, before charging the separate nogood tests.
It makes 32,768 nogood checks per point. The new pair's exact root query
uses 142 counted `CountedOnb` public field entries. These counters have
different operation boundaries, so their sum is not a calibrated total.

## Exact method and verification

The curve is `EC1N83Ckb1h876c2921cb64`, with actual usable normal-basis
weight-five factor base `B=30,977,592`, signed-Frobenius folded
`K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1482 remains a
point-decomposition stage proposal with null candidate and run IDs. The
[protocol](protocol.json) holds the two public points, Q1481 phase-4
leaf-only mask, native-XOR formula, and branch/resource caps fixed. The
[freeze](freeze.json) binds the rootless pair's complete 166-bit leaf
assignment, its identical Q1481 sample on both points, the exact S3
oracle, and the Q1481 source and inputs before building the patched
binary.

The [patch](build.py) returns a conflict from WDSat propagation only when
all 166 leaf bits match that exact rootless assignment. A positive-bit
prefilter changes cost but not the match condition. Both leaves are
nonzero, each has normal-basis weight five, and the frozen exact S3
quadratic has no middle-coordinate root for them. This makes the cut valid
for every target using this curve and field representation. The one-pair
lemma was discovered in Q1481; its search and exact-root work remains in
the earlier attempt ledger and is not hidden inside Q1482's per-attempt
counter.

[Validation](validate.py) reconstructs the C patch, rechecks the exact
rootlessness, binary/input/log hashes, nogood checkpoint counters, and
every new returned S3 root. Both new ordinary attempts have status
`CHECKPOINT_TERMINATED`; together they add 13.438 exploratory solver wall
seconds and 1.017 child user CPU seconds to their respective point
ledgers. Host wall and CPU ratios have no isolation receipt.

## Challenge distance and next gate

One reusable rootless-pair cut is too narrow for this branch prefix. The
new pair has two roots, so the next solver test should constrain its
partially assigned middle coordinate to those exact roots, then measure
whether that support clause changes search diversity or propagation work.
The general version should memoize each distinct pair and add rootless or
two-root support as it appears, charging field-root calls and all failed
search. A verified ordinary relation and rank contribution are still
needed before fitting the complete N131 one-target `2^x` work. The
separate Q1462 conditional weight-seven full pair-index model remains
`2^86.1847` counted pair additions, 25.1847 bits above an abstract
`2^61` pair-addition cap in its different unit.

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_rootless_nogood/validate.py
```
