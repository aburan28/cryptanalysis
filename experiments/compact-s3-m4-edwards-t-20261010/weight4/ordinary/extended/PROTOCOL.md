# Q20261010175400: longer ordinary N53 t-S3 solver cell

Replay the exact `Q20261010174500` ordinary public-point formula, with the
same CryptoMiniSat binary, seed, thread count, and one-million-conflict limit.
Only the external wall cap changes from 120 to 1200 seconds. The original
formula, curve, target, exact factor base, and source hashes are inputs.

Freeze source and input hashes before launching. Save raw solver streams,
return status, wall time, child CPU time, peak RSS, and, if SAT, independent
XCNF and signed group-law checks. A wall timeout or solver conflict cap is
`BOUNDED_UNKNOWN`. Timings on this shared host are exploratory. This is a
PDP stage cell, not a complete IC candidate or one-target speedup result.

Run `python3 runner.py freeze`, then `python3 runner.py run`, then
`python3 audit.py`. All outputs refuse overwrite. The auditor checks the
frozen source/input receipts and independently replays any returned model.
