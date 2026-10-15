# ECC2K-130 DP32 restart, 2026-10-15

This is an operational receipt for the authorized campaign restart. The
machine-readable observation is [receipt.json](receipt.json); the files under
[evidence/](evidence/) retain the provider replies, worker failure, Modal call
IDs, client log sample, S3 sync output, ingest excerpt, and public snapshots.
The [SHA-256 manifest](SHA256SUMS) binds those copied evidence files.
The receipts establish collection and publication at their observation times.
They do not establish a comparative throughput advantage or an attack-cost
result.

## Request and observed state

| Requirement | Observation | Evidence |
| --- | --- | --- |
| Resume the challenge walk with safe seed identities | Modal run IDs 8009 and 8010 were newly registered, spawned on the deployed `ecc2k130` app, and were still active when checked. Each produced a DP batch and a 40-byte checkpoint header in the campaign bucket. | [call IDs](evidence/modal-calls.json), [seed registry view](evidence/seed-registry-sanitized.json), [client log sample](evidence/modal-app-logs-sample.txt), [uploader log](evidence/modal-sync-sample.log) |
| Keep the collection connected to the public counters | The live feed moved from 532,391,575 DPs and zero walking slots at 23:13:31 UTC to 532,490,411 DPs and three walking slots at 23:33:51 UTC. A second publication at 23:38:31 UTC rose to 532,502,873 DPs. The increase includes another controller's g7e worker in slot 246; it cannot all be attributed to these two Modal calls. | [before](evidence/live-status-before-points.json), [after](evidence/live-status-recovered.json), [follow-up](evidence/live-status-followup.json), [ingest excerpt](evidence/ingest-log-excerpt.txt) |
| Preserve failed RunPod attempts | One allocated RTX 5090 failed at `cudaSetDevice`, and the seed guard refused to restart its used run from zero. The pod was deleted with HTTP 204 and a subsequent GET returned 404. Two further allocation attempts found no 5090 capacity in Community or Secure Cloud; a later attempt with the earlier PyTorch image also found no capacity. | [failed worker](evidence/pod-a-worker.log), [create](evidence/pod-a-runpod-create.json), [delete](evidence/pod-a-runpod-delete.json), [Community refusal](evidence/pod-b-runpod-create.json), [Secure refusal](evidence/pod-b-secure-runpod-create.json), [later refusal](evidence/pod-c-runpod-create.json) |
| Leave a running supervisor and uploader | `ecc2k130-modal-fleet-20261015` tracks the two deployed call IDs. `ecc2k130-modal-sync` uploads their new records. Both local processes use scratch and state on `/Volumes/SSD990-2`, where space was available. | [fleet launcher](evidence/start-fleet.sh), [sync launcher](evidence/start-sync.sh), [fleet log](evidence/modal-fleet.log) |

The Modal client sample shows approximately 13.5 and 14.6 billion iterations
per second at about 105 seconds into the two runs. Those are interleaved client
progress lines, not a paired benchmark or a full-run average. The runs use
curve 131, DP weight 32, batch 16, 385,024 workers per GPU, a 60-second
checkpoint interval, and four-hour passes. The local driver requests further
passes after a successful checkpoint. Its continued supervision depends on
the Mac and its `tmux` session remaining available; deployed calls continue
through their current pass without a local client.

The RunPod failure was a CUDA device-initialization error at pinned source
`src/main.cu:1392`, before the worker produced a point. Its S3 slot 245 / run
246 record remains preserved; the seed registry's refusal prevents an unsafe
restart without a checkpoint. The failed pod was listed at $0.69 per GPU-hour
while allocated. This receipt does not infer the provider's final bill.

The separately observed g7e worker in S3 slot 246 / run 247 has its own seed
stream and began uploading during this restart. This report records its effect
on the public totals but does not claim it as a resource launched here.

## Status publication

The Mac LaunchAgent `com.adamburan.ecc2k130-dp-ingest` ingested the new objects.
A direct read of `dp_ingest_totals` showed 532,484,758 points and a latest point
time of 23:29:25 UTC while the public file still showed the 23:18:34 snapshot.
The publisher had logged an SSL EOF when opening PostgreSQL. Restarting the
managed agent at 23:31:39 UTC caused the live S3 feed to publish the newer
`COLLECTING` snapshot at 23:33:51 UTC and another at 23:38:31 UTC. The [database check
script](evidence/check-ingest-db.py) prints only the total and wait-event
summary; credentials were not copied into this record.

At the check, the GitHub Pages fallback [status.json](evidence/pages-snapshot-before-refresh.json)
was still generated at 23:18:34 UTC. The page's JavaScript compares timestamps
and selects the newer live S3 feed; its scheduled Pages workflow had a
[successful 23:27 run](https://github.com/aburan28/crypto/actions/runs/38823728105)
before the live publisher recovered. The fallback's later refresh was not yet
observed in this receipt. The [live response headers](evidence/live-feed-cors-headers.txt)
allow the GitHub Pages origin to fetch that S3 JSON.

## Source and recovery pointers

The Modal deployment used clean relevant files at `crypto` commit
`1b874fccb87f891f13f0b7ca4da9922fe260c2da`. Their SHA-256 values were:

| File | SHA-256 |
| --- | --- |
| `ecc2k130/modal_app.py` | `673c7c57ab64878b2cb83798c25e467263d5f0bd810a95d07e3304c69e824070` |
| `ecc2k130/modal_campaign.py` | `9f0e7c5f6f01b369efb785edc59e28069bff71497a216af2211faecac8c7da79` |
| `ecc2k130/modal_sync.py` | `9753217755cf206b5fd592668e1a3d87c7a902e294d3a975ccbe4d98f3fab0b5` |
| `ecc2k130/run.sh` | `9d78cb46e5ba0cf279e8d99088803c34b02f25fa34925b46882be32f19d8d62f` |

The live supervisor state is under
`/Volumes/SSD990-2/cryptanalysis/ecc2k130/runner/research/production/2026-10-15-modal-restart-runtime`.
`modal-calls.json` names the two deployed calls. Before starting another local
driver, inspect the existing `tmux` session and call IDs; a duplicate driver
must not spawn a second process on either run ID. The S3 seed guard also
refuses unsafe reuse. The uploader's `TMPDIR` and state directory are on the
research volume because the Mac system disk was nearly full.

The short-lived campaign-scoped AWS session used for the failed RunPod pod was
deleted from local scratch after pod termination. No API keys, AWS credentials,
or live seed ownership tokens are in this directory.
