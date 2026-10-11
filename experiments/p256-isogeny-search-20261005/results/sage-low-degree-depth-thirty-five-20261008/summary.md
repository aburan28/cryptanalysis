# P-256 low-degree isogeny search through depth thirty-five

## Outcome

The prospectively frozen extension added 528 curves at depth thirty-four and 544
at depth thirty-five, with no overlap against the prior 8,498-curve union. The
explicit registry now contains P-256 plus 9,569 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as a deterministic gzip
archive whose manifest binds the compressed and uncompressed hashes and sizes.

All 1,072 additions received matched-native measurements in 179 root-controlled
blocks. 16 unadjusted short-screen hit(s), with point estimates in
`1.0278x-1.0910x`, entered the frozen fresh 30-trial, two-second holdout. 1
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0219x` with paired 95% interval `1.0012x-1.0431x`.

The complete retained path was evaluated on both ECDLP points for every new holdout-positive candidate. Mean per-key transfer times span `0.014246`-`0.014246` seconds, and every endpoint generator and discrete-log relation verified.
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. Across all 9,570 retained
curves, 228,530 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`243`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,072 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Deterministic archive, uncompressed hash, and byte-identical repack verified. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | exploratory holdout-positive for 1 candidate(s); controlled status unknown | 16 screen hit(s), 1 holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 35 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-34/35 discovery | 460.6822 s | discovery/precomputation |
| Native screening blocks | 4842.2124 s | exploratory per-iteration comparison |
| Fresh holdout | 1047.3351 s | exploratory verification evidence |
| New positive path evaluation on `P` and `Q` | 0.014246-0.014246 s/key | online per-key transfer; 25 samples of 50 repetitions |
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
