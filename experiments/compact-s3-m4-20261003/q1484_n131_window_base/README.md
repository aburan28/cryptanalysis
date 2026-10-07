# Q1484: exact N131 cyclic-window base

The [pre-registered design](design_protocol.json) extends Q1481's exact
Frobenius window-orbit base to the ECC2K-130 field degree 131. The same
long-zero-gap representative rule gives exactly `2^26` raw `x` orbits for
window dimension 27. Rationality, cofactor projection, duplicates, actual
usable points `B`, and folded columns `K` require exhaustive measurement.

The complete point set will be archived as a two-bit status per raw orbit in
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

After a completed archive passes [independent sampled group-law
audit](verify_archive.py), the [uniform-query budget
screen](screen_uniform_query_budget.py) will apply Q1414's necessary
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

An R2 execution must have its own frozen recovery protocol and preserve this
R1 failure. Reconstruct the checkpoint's key set by replaying the frozen
prefix and checking each two-bit status before continuing. Do not treat the
partial key count as a final base measurement.

## Frozen R2 recovery

The [R2 design](design_recovery.json) was committed in `24f61f34` before
implementation. The [recovery protocol](recovery_protocol.json) binds R1's
failure, progress and bitmap hashes, the original source, the R2 enumerator
and auditor sources, the checked Sage runtime, and the resource limits. The
[R2 preflight](r2_preflight.json) recomputed 4,356 archived status ordinals
and checked 64 point projections with the direct group law. R2 will
recompute **every** R1-prefix status and require the same distinct-key count
at ordinal 19,922,944 before proceeding. It writes into a separate scratch
directory and will be archived under `runs/r2/` after completion. R1 remains
an infrastructure failure regardless of R2's outcome.

The [R2 uniform-query screen](screen_uniform_query_budget_r2.py) is prepared
before the R2 census finishes. It will read only a completed `runs/r2/`
receipt and its independent `archive_audit_r2.json`, then apply Q1414's
Markov argument to R2's exact `B` and `K`. Its `2^x` is a necessary
per-query affordability ceiling under a uniform nonidentity target law with
all other costs set to zero. It is neither a measured PDP cost nor a complete
solve projection. The screen remains unexecuted until the R2 archive passes
audit; R1's partial counts supply no inputs to it.
