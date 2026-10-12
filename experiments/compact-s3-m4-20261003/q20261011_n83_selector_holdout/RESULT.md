# Q1476: unseen N83 point reverses the selected selector-polarity ranking

On a new frozen ordinary N83 public point, flipping target-preimage selector
2140 required **91.47% more CNF** and **113.47% more XOR** `set_true` calls
than phase 0 at the same 262,144-left-branch checkpoint. The flip had reduced
both counters by about 15% and 19% on the point used to select it in Q1474
and Q1475. This unseen-point result refutes a universal matched-prefix
advantage for the fixed 2140 flip.

| Workload | Phase | Selector 2140 | CNF calls at 2^18 branches | XOR calls at 2^18 branches | Solver user CPU s, exploratory | Solver wall s, exploratory |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Q1475 selection point `2eb250a29072` | 0 | unchanged | 76,940,413 | 85,081,823 | 3.144 | 84.263 |
| Q1475 selection point | 1 | flipped | **65,437,262** | **69,215,920** | 2.678 | 73.102 |
| Q1476 unseen point `394256b9f901` | 0 | unchanged | **55,625,977** | **64,761,437** | 2.357 | 61.277 |
| Q1476 unseen point | 1 | flipped | 106,508,678 | 138,243,895 | 4.904 | 131.795 |

The exact curve is `EC1N83Ckb1h876c2921cb64`, with actual usable
factor-base size `B=30,977,592`, signed-Frobenius folded columns
`K=186,612`, stage `PDP4sat`, and `isogeny: "none"`. Q1476 has null
candidate and run IDs because it measures the decomposition stage. The
[input freeze](input_freeze.json) fixed the uniform-nonzero-scalar law,
MT19937 seed `14760083`, exact base, comparison masks, and code before the
target was generated. The [target](target.json) fixes the public point,
four exact cofactor preimages, factor-base digest, and balanced-\(S_3\)
original and width-four XCNF hashes. The [solver freeze](freeze.json) binds
these bytes and the exact Q1473 instrumented binary before either ordinary
attempt. The prior four-mask satisfiable native-XOR control applies to that
unchanged binary.

The checked-Sage input validator independently replayed the fixture scalar,
all four preimages, and byte-for-byte reconstruction of both XCNFs before
solver timing. The final checked-Sage validator passed source/input hashes,
raw branch and propagation checkpoints, status receipts, and the exclusive
phase sum. Both attempts entered search and were terminated after their
complete `Q1473_WORK 262144` checkpoint; each has status
`CHECKPOINT_TERMINATED`. The [attempt ledger](drive_receipt.json) charges
0.230 exploratory seconds for target preimages, 5.390 for the target formula,
193.071 for both solver attempts, and **198.691 seconds** for their
target-dependent phase sum. Solver child user CPU totaled **7.261 seconds**.
Cumulative child peak RSS reached 868,794,368 bytes (828.547 MiB). The host
had no isolation receipt, so wall and CPU timings remain descriptive.

A [posthoc pilot account](pilot_analysis.json) prices a strategy that runs
both masks to `2^15` branches, then restarts the cheaper mask to `2^18`.
The archived pilot counts choose the cheaper full-depth mask on both points.
After charging the two pilots and restart, that strategy uses **20.04% more
CNF calls** and **19.20% more XOR calls** than always running phase 0 across
these two points. This is exact fixed-depth counter accounting under the
declared restart policy, not a measured end-to-end solver strategy or a
target-distribution estimate.

CNF and XOR calls are separate internal work units. The two capped searches
provide no completed ordinary decomposition cost or natural relation-yield
estimate. The complete N83 decomposition exponent, normalized N131
one-target solve exponent, and comparable gap to `2^61` remain null. The
separate Q1462 conditional N131 weight-seven full pair-index model remains
`2^86.1847` counted pair additions, 25.1847 bits above an abstract
`2^61` pair-addition reference under its sampled-base and optimistic-rank
assumptions; its unit and base policy differ from this SAT screen.

The next method experiment should test a target-conditioned polarity choice
inside one solver run, with charged lookahead propagation, or collect a
precommitted ordinary-target panel large enough to estimate whether a static
polarity has a reliable average benefit. A deeper relation search then needs
all failed attempts charged to its point and independent group and rank
verification for any returned relation.

Validate the frozen input, target, and all solver receipts through the
checked launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python /Volumes/SSD990/llm/tmp/q1456-work/experiments/compact-s3-m4-20261003/q20261011_n83_selector_holdout/validate.py
```
