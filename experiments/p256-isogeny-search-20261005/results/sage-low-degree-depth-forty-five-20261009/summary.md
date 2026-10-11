# P-256 low-degree isogeny search through depth forty-five

## Outcome

The prospectively frozen extension added 688 curves at depth forty-four and 704
at depth forty-five, with no overlap against the prior 14,498-curve union. The
explicit registry now contains P-256 plus 15,889 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as 4 ordered shards
of one deterministic gzip stream whose manifest binds every shard plus the
concatenated compressed and uncompressed hashes and sizes.

All 1,392 additions received matched-native measurements in 232 root-controlled
blocks. 32 unadjusted short-screen hit(s), with point estimates in
`1.0222x-1.1281x`, entered the frozen fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0387x` with paired 95% interval `0.9912x-1.0884x`.

No native benchmark blocks were excluded from this stage.

No candidate survived the fresh holdout.

No new depth-44/45 candidate survived holdout, so no additional P,Q path evaluation was triggered. The six earlier exploratory positives remain open for isolated replay, with their previously charged per-key transfers.
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve records Frobenius-order conductor `1` and exact endomorphism-ring
conductor `1`; all path primes have volcano level zero and all edges are
horizontal. Across all 15,890 retained
curves, 485,810 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`239`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,392 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | 4 deterministic shards, concatenated archive hash, uncompressed hash, and byte-identical repack verified. |
| Frobenius/endomorphism conductors and volcano levels | verified class-wide and per candidate | Both conductors are 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | not found within this boundary | 32 screen hit(s), 0 holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 45 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-44/45 discovery | 637.8843 s | discovery/precomputation |
| Excluded wrong-resource native screen | 0.0000 s | protocol-resource mismatch; no trials enter selection |
| Native screening blocks | 6337.4627 s | exploratory per-iteration comparison |
| Fresh holdout | 2038.8229 s | exploratory verification evidence |
| New positive path evaluation on `P` and `Q` | not triggered | no new holdout-positive candidate |
| Exact class-group attempt | running | no result counted at this checkpoint |
| Interrupted exact class-group work | 153833.2071 s | infrastructure loss; no result counted |

CPU affinity separated native timing, traversal, and class-group work, but the
preserved probe shows that this host does not satisfy the repository isolation
gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary`. It is not a universal
nonexistence result and does not enumerate the complete class group.
