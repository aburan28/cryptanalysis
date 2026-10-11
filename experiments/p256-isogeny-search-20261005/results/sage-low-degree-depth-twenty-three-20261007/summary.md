# P-256 low-degree isogeny search through depth twenty-three

## Outcome

The prospectively frozen extension added 336 curves at depth twenty-two and 352
at depth twenty-three, with no overlap against the prior 3,410-curve union. The
explicit registry now contains P-256 plus 4,097 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator.

All 688 additions received matched-native measurements in 115 root-controlled
blocks. 18 unadjusted short-screen hit(s), with point estimates in
`1.0076x-1.0880x`, entered the frozen fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0239x` with paired 95% interval `0.9996x-1.0488x`.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. The coefficient audit found a
minimum addition-chain lower bound of
`244`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 688 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Reproducible iteration-rate advantage | not found within this boundary | 18 screen hit(s), 0 holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No user numerical threshold; mapping and isolation remain open. |
| Entire isogeny class | incomplete | Depth 23 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-22/23 discovery | 297.1651 s | discovery/precomputation |
| Native screening blocks | 3109.1560 s | exploratory per-iteration comparison |
| Fresh holdout | 1171.1859 s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | running | no result counted at this checkpoint |

CPU affinity separated native timing, traversal, and class-group work, but the
host does not satisfy the repository isolation gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
enumerate the complete class group.
