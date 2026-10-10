# P-256 low-degree isogeny search through depth seventeen

## Outcome

The resumed search added 240 curves at depth sixteen and 256 at depth seventeen,
with no overlap against the prior 1,730-curve union. The explicit registry now
contains P-256 plus 2,225 distinct neighbors. Every new record retains its ordered
path, edge maps, short-model isomorphisms, and transported generator.

All 496 additions received matched-native measurements in 83 root-controlled
blocks. 8 unadjusted short-screen hit(s), with point estimates in
`1.0195x-1.1059x`, entered a fresh 30-trial, two-second holdout. 0
candidate(s) reproduced a positive interval. The largest holdout estimate was `1.0097x` with paired 95% interval `0.9899x-1.0300x`.

The deterministic [model-eligibility audit](../model-eligibility-20261006/summary.md)
also shows that Montgomery/Edwards shortcuts are unavailable class-wide and
small-`a` normalization is available to P-256 itself. The unchanged native
backend uses the same candidate-independent operation schedule for every curve.
An explicit replay over all 497 delta records verified 245 maps to `a=1` and
252 maps to `a=3`, including every transported generator.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Frobenius order classification | verified complete | `D_pi` is fundamental, so every curve has the same maximal endomorphism order. |
| Explicit paths and log transport | verified for this boundary | 496 new paths; degrees are coprime to prime `n`; transported generators pass order checks. |
| Exceptional automorphisms or low-norm endomorphisms | refuted class-wide | Exact CM discriminant and norm bound. |
| Unusually cheap standard curve models | refuted class-wide | Odd prime order excludes Montgomery/Edwards; P-256 itself normalizes to `a=1`. |
| Reproducible iteration-rate advantage | not found within this boundary | 8 screen hit(s), 0 fresh-holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No numerical threshold supplied; mapping and full-collision costs remain open. |
| Entire isogeny class | incomplete | Depth 17 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `running`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-16/17 discovery | 262.0092 s | discovery/precomputation |
| Native screening blocks | 2246.1330 s | exploratory per-iteration comparison |
| Fresh holdout | 554.7222 s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | running separately | no result counted at this checkpoint |

CPU affinity separated the native benchmark, traversal, and class-group process,
but the host does not satisfy the repository isolation gate. These timing results
remain exploratory. Screening intervals are unadjusted selection triggers; only
the fresh holdout is used for reproduction.

## Failures and limits

The first depth-17 launch failed before Sage import because a second container
under Docker's `vfs` driver exhausted the writable layer. Its exact command and
traceback summary are retained in [`attempts.json`](attempts.json); the successful
rerun reused the existing Sage container with separate CPU affinity.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
complete a P-256 collision experiment.
