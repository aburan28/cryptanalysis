# P-256 low-degree isogeny search through depth nineteen

## Outcome

The prospectively frozen extension added 272 curves at depth eighteen and 288
at depth nineteen, with no overlap against the prior 2,226-curve union. The
explicit registry now contains P-256 plus 2,785 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator.

All 560 additions received matched-native measurements in 94 root-controlled
blocks. 7 unadjusted short-screen hit(s), with point estimates in
`1.0522x-1.1092x`, entered the frozen fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0137x` with paired 95% interval `0.9919x-1.0360x`.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. The coefficient audit found a
minimum addition-chain lower bound of
`243`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 560 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Reproducible iteration-rate advantage | not found within this boundary | 7 screen hit(s), 0 holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No user numerical threshold; mapping and isolation remain open. |
| Entire isogeny class | incomplete | Depth 19 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-18/19 discovery | 249.9313 s | discovery/precomputation |
| Native screening blocks | 2534.4487 s | exploratory per-iteration comparison |
| Fresh holdout | 493.1057 s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | running | no result counted at this checkpoint |

CPU affinity separated native timing, traversal, and class-group work, but the
host does not satisfy the repository isolation gate. The exact frozen commands
had repository/container working-directory path defects before computation; all
six invocation/reporting/verifier failures and the corrected commands are retained in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
enumerate the complete class group.
