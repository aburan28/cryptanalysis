# Disabling Gaussian matrices leaves the W16 solver gate censored

CryptoMiniSat parsed the same complete, witness-checked N131 W16 native-XOR
formula with `--maxnummatrices=0`, then reached the 115-second safe stop
without a SAT, UNSAT, model, or logged restart line. The bounded result is
`CENSORED_TIME`, with 134,627,328 bytes sampled combined peak RSS.
This isolates one solver-policy change; the exact formula SHA-256 is
`94c7cb24e777840ce9a259c1feb44045674b358ae317bf397be6b7e40ea1849b`.
The [terminal audit](audit.json) binds the frozen command, source hashes,
raw log, formula identity, cap, and status.

The curve is `EC1N131Ckb1heb5f1998f20b`. The
[archived W16 control](../n131_w16_cached_fivepair_20261010/RESULT.md)
has 98,640 variables, 528,425 CNF clauses, and 34,600 native-XOR rows,
with a complete group-correct assignment. This experiment changes only
the solver's maximum number of Gaussian matrices from its installed
default of five to zero; it retains the native-XOR input rows and the
other flags. The [frozen protocol](protocol.json) sets one worker, a
4-GiB combined-RSS cap, and a 115-second solver safe stop. Formula
decompression and hash checking took 1.039 seconds before that solver
interval. The [raw result](result.json) records a 115.054-second solver
subprocess and 3.887 seconds of sampled solver CPU time.

The [cached default-policy run](../n131_w16_cached_fivepair_20261010/query_result.json)
also ended at `CENSORED_TIME` with no logged restart. The host had load
averages above 100 during this replay, so these rows cannot distinguish
expensive initialization from severe scheduling delay or establish a CPU
performance ratio. They show that turning off Gaussian matrices alone did
not produce an observed decomposition under the recorded wall cap.
`candidate_id` remains null; this is a constructed residual solver gate.

The next method experiment should preserve the earlier W16 formula's
statement and variable order while caching its source-mask validity
prefix. A byte-identical formula comparison will establish that its
solver input is unchanged; its separately charged target-dependent build
time will show how much per-prefix work the cache removes before the next
ordinary-query gate.
