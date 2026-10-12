# P-256 low-degree isogeny search through depth thirty-seven

## Outcome

The prospectively frozen extension added 560 curves at depth thirty-six and 576
at depth thirty-seven, with no overlap against the prior 9,570-curve union. The
explicit registry now contains P-256 plus 10,705 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as three ordered shards
of one deterministic gzip stream whose manifest binds every shard plus the
concatenated compressed and uncompressed hashes and sizes.

All 1,136 additions received matched-native measurements in 190 root-controlled
blocks. 14 unadjusted short-screen hit(s), with point estimates in
`1.0130x-1.1056x`, entered the frozen fresh 30-trial, two-second holdout. 2
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0185x` with paired 95% interval `1.0014x-1.0359x`.

| Candidate | Holdout ratio | Paired 95% interval |
| --- | ---: | ---: |
| `p256-j-de71f23f70298ca03961ccbb05e9a6338c4f53069cbceb5b9f816f425e43bb50` | 1.018507x | 1.001429x-1.035876x |
| `p256-j-6aeef18e1f3053ebadceef5f3ea072b6e7d599f7fb00007cde4cb0c9aba80245` | 1.015784x | 1.000181x-1.031630x |

The complete retained path was evaluated on both ECDLP points for every new holdout-positive candidate. Mean per-key transfer times span `0.015213`-`0.016061` seconds, and every endpoint generator and discrete-log relation verified.
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve records Frobenius-order conductor `1` and exact endomorphism-ring
conductor `1`; all path primes have volcano level zero and all edges are
horizontal. Across all 10,706 retained
curves, 270,002 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`240`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,136 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Three deterministic shards, concatenated archive hash, uncompressed hash, and byte-identical repack verified. |
| Frobenius/endomorphism conductors and volcano levels | verified class-wide and per candidate | Both conductors are 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | exploratory holdout-positive for 2 candidate(s); controlled status unknown | 14 screen hit(s), 2 holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 37 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-36/37 discovery | 490.2863 s | discovery/precomputation |
| Native screening blocks | 5133.1875 s | exploratory per-iteration comparison |
| Fresh holdout | 924.2041 s | exploratory verification evidence |
| New positive path evaluation on `P` and `Q` | 0.015213-0.016061 s/key | online per-key transfer; 25 samples of 50 repetitions |
| Exact class-group attempt | running | no result counted at this checkpoint |
| Interrupted exact class-group work | 128200.2071 s | infrastructure loss; no result counted |

CPU affinity separated native timing, traversal, and class-group work, but the
preserved probe shows that this host does not satisfy the repository isolation
gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result contains exploratory holdout-positive evidence but does not establish a controlled speedup. It is not a universal
nonexistence result and does not enumerate the complete class group.
