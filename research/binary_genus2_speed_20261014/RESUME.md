# Live worker and exact resumption

The current-workspace worker was launched as PID 21441, using the immutable
binary `/workspace/measurements/binary-genus2-speed-20261014/bin/cover_rho-campaign`.
Its source is crypto dbd33f00da0a0ac35f285603ec168ad9d91a1d79. A PID or the
startup `active.json` is not sufficient health evidence: check that the process
exists and that the timestamp and work count in `progress.jsonl` advance.
The worker survived the observed workspace reconnection without restarting.

Live paths:

```
/workspace/measurements/binary-genus2-speed-20261014/public/
/workspace/measurements/binary-genus2-speed-20261014/campaign/
/workspace/measurements/binary-genus2-speed-20261014/campaign/worker.log
```

The scalar witness file is outside these public/solver directories and is not
part of the frozen archive. Do not copy it into inputs or solver working data.

Pause, wait for the marker before any heavy work, then continue:

```sh
touch /workspace/measurements/binary-genus2-speed-20261014/campaign/PAUSE
# Wait until campaign/paused.json exists and says paused_with_checkpoints.
# Copy/checkpoint/archive or do the authorized heavy work.
rm /workspace/measurements/binary-genus2-speed-20261014/campaign/PAUSE
```

An orderly stop uses `campaign/STOP`. Keep the stopped-run record; remove the
control file only when explicitly resuming. To resume in the current workspace
when the old process is no longer running:

```sh
/workspace/measurements/binary-genus2-speed-20261014/bin/cover_rho-campaign run \
  --public /workspace/measurements/binary-genus2-speed-20261014/public \
  --out /workspace/measurements/binary-genus2-speed-20261014/campaign --cpu 4
```

Do not start a second copy while the first still holds the benchmark lock.
No global step cap is imposed. A scheduling quantum does not restrict the
scalar space or discard the distinguished-point table.

To move to another machine, copy the complete public directory and the campaign
checkpoint/candidate/verification files after an acknowledged pause. Build the
pinned source using the committed standalone lockfile. Choose an available
complete CPU core on that machine; CPU 4 is specific to the original worker.
Start `cover_rho run --public COPIED_PUBLIC --out COPIED_CAMPAIGN --cpu CPU`.
Hash and retain both the old and new binary, source and host records. Existing
checkpoints validate the public-job identity and reconstruct cached divisors
from the saved image points. New-host timing is a separate run, not an extension
of the old host's performance claim.

The frozen snapshots under `runs/run-20261014T1901Z/`,
`runs/run-20261014T2034Z/`, `runs/run-20261014T2148Z/` and
`runs/run-20261014T2250Z/` are immutable. The latest paused at Unix
1792018309 and contains all eight a=1 completions in each of the three
matched arms: 24 resumable completions. The final native Q_7 also passed
one further separate-process E/Jacobian check. All a=0 checkpoints remain
censored, with later targets queued. The a=1 streams are complete and the
original worker continues the a=0 streams without an overall step cap.
Earlier receipts remain unchanged. This is the original worker and public
target set; no discarded-table restart or witness access was used.

Live identity was checked using PID 21441's command line, process start tick
1667143, CPU-time/progress advancement, affinity and acknowledged pause.
The latest pause observed 03:06:55 CPU time on that same process; its a=0
checkpoints retained 1,147,759,082 E steps, 1,142,115,358 inverse/E steps and
11,707,378 native steps, without candidates.
`/proc/21441/exe` resolution was denied by the runtime; the exact limitation
and immutable on-disk binary hash are in the new archive's `ARCHIVE.md`.
Do not use the archived startup `active.json` or a PID alone as health proof.
Write future snapshots and reports under new run IDs.
Current-worker persistence is not guaranteed. The [a=0 compute problem](../../problems/binary-genus2-a0-full-solve-compute.md)
keeps the original full-subgroup requirement and the measured resource gap open.
