# Q1473: selector-polarity propagation counters

Q1473 adds source-bound first-branch masks for the two exact N83 target-preimage
selector IDs, 2140 and 2141, and counts CNF and XOR `set_true` calls at every
power-of-two WDSat left-branch checkpoint. The four masks share the Q1472
ordinary public point, compact balanced-S3 XCNF, exact factor base, and
`selector_pair_mids` variable order. A satisfiable 2,141-variable native-XOR
control returned a replayed SAT model under all four masks; its final
CNF/XOR call counts and branch checkpoints were independently reproduced by
the validator.

The full-lock N83 control for phase 0 reached `Q1458_AFTER_XOR_INIT`, then
hit the frozen 600-second wall limit before `Q1458_SEARCH_START`. It used
13.175 solver user CPU seconds, 1.459 system CPU seconds, and 848,117,760
bytes peak RSS on the heavily contended host. Its recorded status is
`CENSORED_BEFORE_SEARCH`. The control gate stopped the schedule before any
ordinary phase, so this screen adds **zero ordinary-target attempts**. The
[drive receipt](drive_receipt.json) retains that stop and carries forward
Q1472's 3,361.243 exploratory target-dependent wall seconds on the same
public point. [The analysis](analysis.json) keeps the new measured ordinary
work and the complete N83/N131 solve exponents null.

| Measurement | Phase 0 full-lock control | Four-mask native-XOR correctness control |
| --- | --- | --- |
| Result | `CENSORED_BEFORE_SEARCH` | 4 independently replayed SAT models |
| Left-branch checkpoints | none | exact per-mask traces in `smoke_receipt.json` |
| CNF/XOR work counters | no search checkpoint | final and checkpoint counts in `smoke_receipt.json` |
| Solver user CPU | 13.175 s | correctness only; timing excluded |
| Wall limit | 600 s reached | 60 s safety cap per mask; all completed |

The mathematical identity remains `EC1N83Ckb1h876c2921cb64`, actual
factor-base size `B=30,977,592`, signed-Frobenius folded columns
`K=186,612`, workload `2eb250a29072`, stage `PDP4sat`, and
`isogeny: "none"`. `Q1473` is a stage proposal with null candidate and run
IDs. [The protocol](protocol.json) and [freeze](freeze.json) bind the reused
Q1472 target and archives, source hashes, runtime receipt, four exact masks,
and resource limits. [The build receipt](build_receipt.json) records the
pinned WDSat source, selector patch, instrumented call sites, and binary hash.

The checked-Sage [validator](validate.py) passed exact target scalar and
four-preimage replay, byte-for-byte reconstruction of both N83 XCNFs,
source/binary/receipt hashes, the censored-control classification, and a
second execution of all four native-XOR correctness controls. The compiler
accepted the patched C source; the full N83 control yielded no comparable
selector-work row because search did not begin.

The separate Q1462 conditional N131 weight-seven full pair-index model is
`2^86.1847` counted pair additions, 25.1847 bits above an abstract `2^61`
pair-add reference. Those pair additions are distinct from Q1473's CNF and
XOR propagation-call units. A complete N131 work exponent still requires an
ordinary relation, useful-row yield and rank, final matrix and target costs,
and a common operation calibration.

The next execution gate is to rerun the frozen four-mask comparison on a host
where the full-lock control reaches search under a documented isolation
receipt. The runner stops at the first infrastructure censor and charges all
completed ordinary attempts to the same point. Any selected mask then needs
a new previously unseen N83 target before a one-target speedup comparison.
