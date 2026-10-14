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

The frozen snapshot under `runs/run-20261014T1901Z/` is immutable. Its candidate
and verification records identify completed targets; other checkpoints are
censored observations. Write future snapshots and reports under new run IDs.
Current-worker persistence is not guaranteed. The [a=0 compute problem](../../problems/binary-genus2-a0-full-solve-compute.md)
keeps the original full-subgroup requirement and the measured resource gap open.
