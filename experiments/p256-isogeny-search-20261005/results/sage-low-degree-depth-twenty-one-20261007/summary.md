# P-256 low-degree isogeny search through depth twenty-one

## Outcome

The prospectively frozen extension added 304 curves at depth twenty and 320
at depth twenty-one, with no overlap against the prior 2,786-curve union. The
explicit registry now contains P-256 plus 3,409 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator.

All 624 additions received matched-native measurements in 104 root-controlled
blocks. 5 unadjusted short-screen hit(s), with point estimates in
`1.0280x-1.0925x`, entered the frozen fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `0.9982x` with paired 95% interval `0.9812x-1.0155x`.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. The coefficient audit found a
minimum addition-chain lower bound of
`247`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 624 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Reproducible iteration-rate advantage | not found within this boundary | 5 screen hit(s), 0 holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No user numerical threshold; mapping and isolation remain open. |
| Entire isogeny class | incomplete | Depth 21 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-20/21 discovery | 280.2169 s | discovery/precomputation |
| Native screening blocks | 2829.0183 s | exploratory per-iteration comparison |
| Fresh holdout | 369.7782 s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | running | no result counted at this checkpoint |

CPU affinity separated native timing, traversal, and class-group work, but the
host does not satisfy the repository isolation gate. The attempts ledger retains
the environment-restart interruption and every other unsuccessful invocation in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
enumerate the complete class group.
