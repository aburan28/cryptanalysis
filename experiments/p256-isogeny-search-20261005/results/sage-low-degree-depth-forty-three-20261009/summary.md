# P-256 low-degree isogeny search through depth forty-three

## Outcome

The prospectively frozen extension added 656 curves at depth forty-two and 672
at depth forty-three, with no overlap against the prior 13,170-curve union. The
explicit registry now contains P-256 plus 14,497 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as three ordered shards
of one deterministic gzip stream whose manifest binds every shard plus the
concatenated compressed and uncompressed hashes and sizes.

All 1,328 additions received matched-native measurements in 222 root-controlled
blocks. 33 unadjusted short-screen hit(s), with point estimates in
`1.0319x-1.1335x`, entered the frozen fresh 30-trial, two-second holdout. 2
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0276x` with paired 95% interval `1.0063x-1.0493x`.

A container-only launch used CPU 2 after the managed-environment transition made
CPU 0 unavailable inside that container. It was stopped after
5 complete blocks and 135.9674
seconds because the frozen protocol requires host CPU 0. Those relation-verified
artifacts are preserved but excluded from selection and all accepted aggregates.

| Candidate | Holdout ratio | Paired 95% interval |
| --- | ---: | ---: |
| `p256-j-45f3bf4b5d05be2afe493ea0ef3f072ab6631ceae34c030cd9e2d33b330b0c00` | 1.027571x | 1.006283x-1.049309x |
| `p256-j-01f5c5797fd841b9000c05165f372bd6ac33db30bf1b5ab80a3ecbec4f1bf063` | 1.024525x | 1.000520x-1.049106x |

The complete retained path was evaluated on both ECDLP points for every new holdout-positive candidate. Mean per-key transfer times span `0.019670`-`0.019692` seconds, and every endpoint generator and discrete-log relation verified.
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve records Frobenius-order conductor `1` and exact endomorphism-ring
conductor `1`; all path primes have volcano level zero and all edges are
horizontal. Across all 14,498 retained
curves, 423,858 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`245`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,328 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Three deterministic shards, concatenated archive hash, uncompressed hash, and byte-identical repack verified. |
| Frobenius/endomorphism conductors and volcano levels | verified class-wide and per candidate | Both conductors are 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | exploratory holdout-positive for 2 candidate(s); controlled status unknown | 33 screen hit(s), 2 holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 43 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-42/43 discovery | 648.5491 s | discovery/precomputation |
| Excluded wrong-resource native screen | 135.9674 s | protocol-resource mismatch; no trials enter selection |
| Native screening blocks | 6053.0621 s | exploratory per-iteration comparison |
| Fresh holdout | 2096.5070 s | exploratory verification evidence |
| New positive path evaluation on `P` and `Q` | 0.019670-0.019692 s/key | online per-key transfer; 25 samples of 50 repetitions |
| Exact class-group attempt | running | no result counted at this checkpoint |
| Interrupted exact class-group work | 153833.2071 s | infrastructure loss; no result counted |

CPU affinity separated native timing, traversal, and class-group work, but the
preserved probe shows that this host does not satisfy the repository isolation
gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result contains exploratory holdout-positive evidence but does not establish a controlled speedup. It is not a universal
nonexistence result and does not enumerate the complete class group.
