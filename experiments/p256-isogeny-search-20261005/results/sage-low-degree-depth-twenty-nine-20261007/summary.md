# P-256 low-degree isogeny search through depth twenty-nine

## Outcome

The prospectively frozen extension added 432 curves at depth twenty-eight and 448
at depth twenty-nine, with no overlap against the prior 5,666-curve union. The
explicit registry now contains P-256 plus 6,545 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as a deterministic gzip
archive whose manifest binds the compressed and uncompressed hashes and sizes.

All 880 additions received matched-native measurements in 147 root-controlled
blocks. 19 unadjusted short-screen hit(s), with point estimates in
`1.0201x-1.0908x`, entered the frozen fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0070x` with paired 95% interval `0.9892x-1.0250x`.

No new depth-28/29 candidate survived holdout, so no additional P,Q path evaluation was triggered. The depth-25 exploratory positive remains open for isolated replay, with its previously charged 0.011433-second per-key transfer.
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. The coefficient audit found a
minimum addition-chain lower bound of
`246`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 880 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Deterministic archive, uncompressed hash, and byte-identical repack verified. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | not found within this boundary | 19 screen hit(s), 0 holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 29 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-28/29 discovery | 405.3485 s | discovery/precomputation |
| Native screening blocks | 3983.8008 s | exploratory per-iteration comparison |
| Fresh holdout | 1232.8245 s | exploratory verification evidence |
| New positive path evaluation on `P` and `Q` | not triggered | no new holdout-positive candidate |
| Exact class-group attempt | running | no result counted at this checkpoint |

CPU affinity separated native timing, traversal, and class-group work, but the
preserved probe shows that this host does not satisfy the repository isolation
gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary`. It is not a universal
nonexistence result and does not enumerate the complete class group.
