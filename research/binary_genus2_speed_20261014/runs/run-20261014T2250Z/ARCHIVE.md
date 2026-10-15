# Original campaign snapshot, follow-up beginning 2026-10-14 22:50 UTC

The original worker acknowledged this archival pause at Unix 1792018309
(22:51:49 UTC), with status `paused_with_checkpoints`. All eight a=1 targets
are now complete in all three matched resumable arms. This snapshot adds the
last native target, Q_7, to the preceding seven-target panel. The three earlier
run directories remain immutable.

Live identity checks observed PID 21441, kernel process name `cover_rho-campa`,
the original command line, start tick 1667143 and CPU 4. CPU time advanced
from 03:06:07 to 03:06:28 before the pause, and to 03:06:55 at acknowledgment.
Progress timestamps advanced from Unix 1792018259 to 1792018281, with
retained a=0 work beyond the preceding snapshot. Startup `active.json` was
not treated as health evidence. Executable-link resolution was previously
denied by the runtime; no stronger `/proc/PID/exe` check is claimed. Immutable
on-disk binary and source hashes were rechecked. Campaign binary SHA-256 is
`e02c63d3fc033ce6ccc007aca13cd74aa0c342572744bce7869e984585525231`.

There are 24 verified resumable completions: eight E, eight inverse/E and
eight native Jacobian targets for a=1. Each retains its original separate
E/Jacobian verification process receipt. The newly completed native Q_7
also passed one further standalone invocation:

```
cover_rho-campaign verify --job public/a1-7.json \
  --result campaign/a1-7-jacobian.candidate.json \
  --out FRESH_RECEIPT
```

That receipt is in `followup-verification/`; it uses the recovered candidate,
not the held-out witness. Earlier successful checks were not rerun. The 27
optimized references and prefix-calibration controls repeat earlier evidence,
not new executions or independent targets.

The completed native Q_7 has 10,442,347 steps, matching both other arms.
Recorded active-search seconds: E 9.268307496, inverse/E 9.153279320,
native checked Cantor plus conversions 1160.138869297. The a=1 subgroup is
53 bits, despite the 83-bit field. Completing this panel does not establish
admissible timings, a complete common priced cost or an ECDLP advantage.

All a=0 full solves remain unfinished. First-target checkpoints retain
1,147,759,082 E steps, 1,142,115,358 inverse/E steps and 11,707,378 native
steps, without candidates; later targets are queued. These are censored work
counts, not completed durations. Complete distinguished-point tables, lane
coefficients and histories, cursors, seeds and identities are retained.
Archived PAUSE markers describe this boundary, not the worker's later state.

Public inputs, reference/calibration and restart records, source/binary
bindings and live campaign files were explicitly copied. No witness or binary
is included. Native Rust `cover_summary-campaign` generated `snapshot.json`.
`SHA256SUMS` binds every archived file except itself. Source remains crypto
dbd33f00da0a0ac35f285603ec168ad9d91a1d79. The cryptanalysis copy is the
same performance evidence, not an independent campaign or host replay.

All measurements remain L0 active-search observations. No admitted speedup,
common priced cost, ecbench audit or independent-host performance replay
exists. Both a=0 durable-compute and ecbench-adapter exit criteria remain
open. `conductor check` was attempted before editing and returned 127 because
the executable is unavailable. Original inputs, m=83, both prime orders and
all walk parameters are unchanged; no paid resources were provisioned.
