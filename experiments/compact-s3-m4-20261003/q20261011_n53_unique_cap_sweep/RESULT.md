# Q1453: the frozen Python prefix sweep reached its table-build cap

The deterministic 500,000/1,000,000/2,000,000-state N53 quotient-pair
sweep exposed a table-build throughput limit on the contended local host.
Its 1,200-second external wall cap arrived while `OrbitKey.canonical`
was still constructing the table. The supervisor interrupted the worker;
`exit-status.json` records exit code 130 and `stderr.log` records the
interrupted stack. The runner had not written a measurement checkpoint, so
completed table states, ordinary query count, and rank are **unknown** for
this attempt.

The exact curve, workload, factor base, and proposal-stage names are in
`protocol.json`; `freeze.json` binds source and input hashes. This attempt
is `PRODUCER_INTERRUPTED_AT_EXTERNAL_WALL_CAP`, not a query no-hit result.
Its table-loop cap check occurred only after construction, which the next
implementation corrected.

Q1454 uses the same shuffled orbit-pair schedule and exact query-index
stream with native ONB arithmetic. It checks the wall cap during table
construction and records all three table prefixes, completing the full
1.5-million-query horizon under the declared resource cap. See the adjacent
`q20261011_n53_native_pair/RESULT.md` for the measured rank and work.
