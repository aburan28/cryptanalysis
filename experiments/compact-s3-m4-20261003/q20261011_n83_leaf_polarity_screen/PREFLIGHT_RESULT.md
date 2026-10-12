# Q1480 preflight: the frozen mask schedule is absent from the pinned binary

The attempted N83 polarity sweep stopped after phase 1 on both public
points. Phase 0 reached the 32,768-branch checkpoint, but phase 1 exited
before solver search with `Q1473_BAD_SELECTOR_ORDER` and status
`PRODUCER_FAILURE`. The frozen Q1472 random-mask schedule assigns 250
variables to phase 1; the pinned Q1479 binary contains a separate
Q1473 selector-only schedule with **one** phase-1 flip, selector 2140.
Its first polarity pass negates that selector, and the following Q1473
pass requires the unnegated selector to be present. The binary therefore
rejects this attempted composition before search.

| Public workload | Phase | Frozen intended flips | Binary-reported flips | Status | Search started |
| --- | ---: | ---: | ---: | --- | --- |
| `2eb250a29072` | 0 | 0 | 0 | `CHECKPOINT_TERMINATED` | yes |
| `2eb250a29072` | 1 | 250 | 1 | `PRODUCER_FAILURE` | no |
| `394256b9f901` | 0 | 0 | 0 | `CHECKPOINT_TERMINATED` | yes |
| `394256b9f901` | 1 | 250 | 1 | `PRODUCER_FAILURE` | no |

The [frozen protocol](protocol.json), [source/input freeze](freeze.json),
[attempt ledger](drive_receipt.json), and raw logs remain intact. The
phase-1 rows are implementation failures, not measurements of the proposed
leaf-polarity masks or mathematical exclusions. Their target-dependent
startup and failure time belongs to each point's attempt ledger. Q1481
will compile a new leaf-only mask schedule into a new hash-bound binary
and use `Q1472_PHASE_INDEX=0` to leave the older selector masks inactive.
