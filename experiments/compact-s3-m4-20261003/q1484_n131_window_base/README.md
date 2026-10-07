# Q1484: exact N131 cyclic-window base

The [pre-registered design](design_protocol.json) extends Q1481's exact
Frobenius window-orbit base to the ECC2K-130 field degree 131. The same
long-zero-gap representative rule gives exactly `2^26` raw `x` orbits for
window dimension 27. Rationality, cofactor projection, duplicates, actual
usable points `B`, and folded columns `K` require exhaustive measurement.

The complete point set is archived as a two-bit status per raw orbit in
the deterministic Q1481 representative order, together with the frozen
projection code and the SHA-256 digest of sorted unique projected orbit keys.
This compact encoding reconstructs every subgroup-usable point by applying
the declared [4] projection and expanding both signs and all Frobenius
powers. It avoids putting a several-hundred-megabyte raw key list in Git.

This is a factor-base geometry experiment. It retains the exact curve ID
`EC1N131Ckb1h6816f880945e`, `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. A nominal dimension is not an `fb<B>` count. No N131
decomposition or complete `2^x` is claimed by this work.

## Frozen execution

The design was committed in `5f7404ed`. Commit `dc410eb9` froze the
enumerator, archive auditor, exact curve and field references, checked Sage
runtime, limits, and [execution protocol](protocol.json) before the first
exhaustive run. The [preflight](preflight.json) checked 4,096 raw-orbit
ordinals and status encodings, including 32 direct N131 group projections.
The enumerator writes progress and a partial bitmap every `2^20` raw orbits;
an incomplete attempt remains an attempt and supplies no actual `B` or `K`.

The completed archive passed an [independent sampled group-law
audit](archive_audit_r2.json), and the [uniform-query budget
screen](uniform_query_budget_r2.json) applies Q1414's necessary
rank-supply bound to this exact changed base. Its per-query `2^x` is an
optimistic affordability ceiling with all other costs set to zero. It is
separate from the still-unknown complete-solve work.

The [full N53 encoding replay](n53_encoding_replay.json) independently
iterates all 8,192 Q1481 raw window orbits, constructs the two-bit archive,
reconstructs its point set, and matches Q1481's archived 4,060 columns,
430,360 usable points, and packed-key file byte for byte. This control uses
N53's **exact cofactor 428**; N131's cofactor is 4. An initial unarchived
control draft used 4 on N53 and failed its key comparison, prompting this
correction. The N131 enumerator and frozen protocol already use 4.

A supplementary [high-span N131 preflight](high_span_preflight.json) checks
98 deterministic masks with spans 14 through 27 against direct group-law
projection; 48 have rational lifts and all 98 checks pass. This covers mask
shapes beyond the low-span cases in the original frozen preflight. It is a
sampled correctness control, not an estimate of the full base size.

## R1 infrastructure failure

The first exhaustive attempt, `Q1484R1`, stopped with `OSError: [Errno 28]
No space left on device` while writing a progress bitmap. The durable
[postmortem record](runs/r1/failure.json) identifies the failure site and
hashes the saved [progress](runs/r1/progress.jsonl) and
[partial bitmap](runs/r1/status_flags.partial). The last complete checkpoint
covers 19,922,944 of 67,108,864 raw orbits and contains 9,963,049 distinct
projected orbit keys **so far**. The attempt did not finish and does not
establish the final `B`, `K`, point-set digest, or any solve cost.

The separately frozen R2 recovery preserved this R1 failure. It
reconstructed the checkpoint's key set by replaying the frozen prefix and
checking each two-bit status before continuing. The partial key count is not
a final base measurement.

## Frozen R2 recovery

The [R2 design](design_recovery.json) was committed in `24f61f34` before
implementation. The [recovery protocol](recovery_protocol.json) binds R1's
failure, progress and bitmap hashes, the original source, the R2 enumerator
and auditor sources, the checked Sage runtime, and the resource limits. The
[R2 preflight](r2_preflight.json) recomputed 4,356 archived status ordinals
and checked 64 point projections with the direct group law. R2 recomputed
**every** R1-prefix status and matched 9,963,049 distinct keys at ordinal
19,922,944 before continuing. Its complete [receipt](runs/r2/receipt.json),
[status bitmap](runs/r2/status_flags.bin), and
[progress](runs/r2/progress.jsonl) are archived. R1 remains an
infrastructure failure regardless of R2's outcome.

## R2 exact census and necessary work screen

R2 enumerated all **67,108,864** raw x-orbits. The [archive
audit](archive_audit_r2.json) checked the complete bitmap count and hash,
replayed the R1 prefix, and independently checked 232 sampled direct
group-law cases (126 rational, zero identity projections). The sorted
projected-set digest below comes from the source-bound producer receipt; the
auditor did not independently recompute that full sorted digest.

| Exact property | R2 result |
| --- | ---: |
| Subgroup-usable points before folding, `B` | 8,790,494,834 |
| Signed-Frobenius columns, `K` | 33,551,507 |
| Sorted projected-set SHA-256 | `d3fa5abbd34df91d48731d283b4960f6110d8202c452a8bd349baa907bb4a331` |
| Bitmap SHA-256 | `97c1c7a0df5a6548d7be8c208dfb2d36921fe96173315735edfacc6ab0b155c2` |
| Construction wall time, exploratory | 4,658.109 s |
| Peak RSS | 3,120,365,568 bytes |

The [R2 uniform-query screen](uniform_query_budget_r2.json) used only the
completed receipt and passing audit. For uniform nonidentity subgroup
queries, it gives an **upper bound** of 0.365572 expected four-point
representations per query. If every representation were returned, every row
were novel, all `K` rows came from these queries, and every other cost were
zero, the following minimum query counts and necessary per-query ceilings
would apply to a total budget below `2^61` in the same charged unit:

| Rank-supply criterion | Minimum queries | `log2` queries | Per-query ceiling |
| --- | ---: | ---: | ---: |
| 50% chance of rank `K` | 45,889,088 | 25.452 | `2^35.548` |
| 95% chance of rank `K` | 87,189,268 | 26.378 | `2^34.622` |
| Expected rank at least `K` | 91,778,176 | 26.452 | `2^34.548` |

These are necessary affordability ceilings under the stated query law, not
measured PDP costs or an estimate of the complete N131 solve. Natural
relation yield, novel rank, final sparse matrix cost, target descent, and
independent scalar replay remain unmeasured. Consequently the complete
N131 `2^x` remains `null`, and this result does not admit a challenge run.
