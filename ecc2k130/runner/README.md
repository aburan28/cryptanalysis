# ECC2K-130 runner

The Certicom challenge client and its worker supervisor now live here, independently
of the `crypto` checkout. Production uses the legacy Frobenius walk at **DP weight
32**, contributing to the existing **`ecc2k-130`** RDS collision pool. The faster
table-walk research profile remains available as `make gpu-rtx-pro6000-22b`;
its 22.101 billion updates/sec measurement applies to a different walk and is
not the production fleet's speed. See [SOURCE.md](SOURCE.md)
for provenance and [ENGINE.md](ENGINE.md) for the archived engine notes.

For cloud collection, use **`cloud.py`**, **`modal_worker.py`**, and
**`deploy/Dockerfile`**. Both providers run the same supervisor:

```text
CUDA client → local DP records → immutable S3 delta → direct RDS report_dp calls
                 checkpoint ──────────────────────→ S3 (after both DP sinks succeed)
```

The worker leases a run ID, downloads its checkpoint, starts one GPU process,
periodically publishes records and checkpoints, then stops gracefully at the
configured duration. There is no ingester, merge daemon, control server, or fleet
provisioning service to start. RDS records possible collisions; the runner does
not launch a separate service to replay or resolve cross-worker collisions.

## Prerequisites and configuration

Use an existing S3 bucket and the existing PostgreSQL/RDS rho-dp schema. This
migration does not create or modify database schema. `preflight` checks for
`rho_campaigns` and `report_dp`; `smoke` tests the actual report contract.

| Environment variable | Meaning |
| --- | --- |
| `ECC_BUCKET` | Campaign bucket; required in cloud mode |
| `AWS_DEFAULT_REGION` | Bucket region |
| AWS credential variables or role | Must permit `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`; include `AWS_SESSION_TOKEN` for temporary credentials |
| `RHO_DP_DSN` or `DATABASE_URL` | PostgreSQL DSN; use TLS and a database user allowed to register a campaign and execute `report_dp` |
| `ECC_PREFIX` | S3 checkpoint/lease namespace; image default `campaigns/ecc2k130-frobenius32-120k-v1` |
| `RHO_CAMPAIGN` | Legacy fallback only; the production configuration's `campaignId` takes precedence |
| `ECC_RDS_SECURITY_GROUP` | Optional Modal-only managed TCP 5432 ingress for each worker's public IPv4 `/32`; set on the launcher |
| `ECC_ROOT` | Writable worker state directory; container default `/workspace/ecc2k130` |
| `ECC_GPU` | Integer device index inside the provider's visible GPU set; default `0` |
| `ECC_TABLE` | Leave unset for this namespaced campaign; leases use S3 conditional writes |

Provide secrets through the provider's secret/environment settings. Do not put
them in the image, `campaign.json`, build arguments, or source control. The cloud
entry point requires RDS unless `--s3-only` is explicitly selected.

`run` conditionally initializes [aws/campaign.json](aws/campaign.json) under the
configured S3 prefix. Modal `smoke` does the same so a new deployment can be
tested before allocating GPUs. Existing configuration is never overwritten.
The bucket's older root-level checkpoints and the archived table-walk campaign
remain separate. The new storage prefix uses the existing `ecc2k-130` RDS pool.

The container builds the packed GF(2^131) Frobenius backend with batch **16**,
block size **640**, min-blocks **1**, **120,320** worker threads, and DP weight
**32**. [build.json](build.json) records the geometry and walk/checkpoint identity;
`preflight` rejects incompatible remote configuration. Slots 0–3 use run IDs
12,000–12,003. The RDS campaign is `ecc2k-130`. Its historical metadata is
validated without rewriting it; startup also checks the root S3 campaign's
DP weight and the binary hash used for compatibility validation. A changed
shared configuration requires a new compatibility check.

The production build uses four-warp collective inversion and the validated
Frobenius arithmetic settings. Build it with `make -C ecc2k130/runner gpu-production`
(or `gpu-frobenius32-120k`). Its three-run screening median was **17.453024
billion updates/s** at 120,320 workers, excluding cloud reporting overhead.
It starts a fresh population in the new namespace; larger checkpoints remain
archived in their original locations. The separate `gpu-frobenius32-fast`
target retains scalar inversion for 385,024-worker populations. Measurements and
checkpoint compatibility receipts are in
[the reconciliation report](research/DP-RECONCILIATION.md).

The current rollout runs eight RTX PRO 6000 workers in
[Modal app ap-BfNPp3WMk8aVi0GYaDdkbw](https://modal.com/apps/a-buran28/main/ap-BfNPp3WMk8aVi0GYaDdkbw)
from 23:57 UTC on 2026-09-25 until 22:57 UTC on 2026-09-26. Runs 12,000–12,004
resumed from their S3 checkpoints and runs 12,005–12,007 started fresh. It replaced
a rollout that had shrunk to one worker. Its two-hour check measured 16.8–17.7 billion
updates/s per worker, 138.9 billion in total, with no restarts and seed-matching
RDS samples. See the [deployment receipt](research/production/2026-09-25-8worker-deployment.json)
and the [validation receipt](research/production/2026-09-25-8worker-deployment-validation.json)
for the rebuilt binary.

The earlier 2026-09-25 rollout resumed runs 12,000–12,003 from their S3 checkpoints on
four RTX PRO 6000 workers in
[Modal app ap-OZBcIVgzRNv4khVa0Hojt3](https://modal.com/apps/a-buran28/main/ap-OZBcIVgzRNv4khVa0Hojt3).
It was stopped before its 03:36 UTC deadline to make way for the eight-worker
rollout. It was the first rollout of the fused Frobenius build
(profile v2). That exact image passed the legacy compatibility gate in
[its validation receipt](research/production/2026-09-25-fused-deployment-validation.json).
The first launch reserved four CPU cores per worker. At 04:35 UTC the fleet was
relaunched with the two-core request. After the relaunch, the four clients
reported 69.48 billion updates/s in total, zero drops, advancing checkpoints
and seed-matching RDS samples. See the
[relaunch receipt](research/production/2026-09-25-cpu2-deployment.json) and the
[first launch receipt](research/production/2026-09-25-fused-deployment.json).

The 2026-09-21 rollout ran four RTX PRO 6000 workers in
[Modal app ap-89OUG2uEQpkkKtdd1WO8ru](https://modal.com/apps/a-buran28/main/ap-89OUG2uEQpkkKtdd1WO8ru).
Run 12,000 resumed the successful three-minute canary; runs 12,001–12,003 started
fresh. The older volume-backed jobs were stopped gracefully, with their final
checkpoints and 71,194,498 stored DP records verified in the persistent volume.
See the [deployment receipt](research/production/2026-09-21-120k-deployment.json)
for runtime identities, validation and live storage/database checks.

The existing [public crypto dashboard](https://aburan28.github.io/crypto/status/)
reports `ecc2k-130` at DP weight **32**. Its feed comes from `dp_ingest.py` on the
legacy Runpod ingest pod. Since 2026-09-25 the deployed copy also counts this
fleet: checkpoints from namespaced campaigns that share the collision table, and
points that workers report directly through `report_dp`. It also measures
"walking now" over about an hour instead of an ever-growing window. The
deployed file (`s3://…/aws/dp_ingest.py`, sha256 `58460b7a…`) is ahead of the
`crypto` repository; the change is in
[the dashboard patch](research/production/2026-09-25-dp-ingest-namespaced.patch)
and its [receipt](research/production/2026-09-25-dp-ingest-namespaced.json).
Its "GPUs running" count means a checkpoint was uploaded within 30 minutes;
copying an old checkpoint can refresh that timestamp after a worker stops.
Use the Modal app's worker logs and this campaign's S3 leases/RDS rows to check
the new fleet. Archived `ecc2k130-table8-22b-v1` records have a different walk
identity and must remain separate; they are not relabeled or merged by this
production switch.

The ingest pod is also the Runpod CPU walker. When it stops, the page freezes at
its last publish, as it did when every Runpod pod went silent at 23:04 UTC on
2026-09-25. `modal_ingest.py` runs the same deployed `aws/dp_ingest.py`, with the
pod's arguments, in a one-core Modal container for at most 23 hours:

```sh
export ECC_RDS_SECURITY_GROUP=YOUR_RDS_SECURITY_GROUP
modal run --detach ecc2k130/runner/modal_ingest.py --seconds 82800
```

It downloads the S3 copy at start and logs its sha256. It connects with the
Modal secret's `RHO_DP_DSN`, the same `rho` role as the pod's `rho/dp-rds` secret.
It opens its own `/32` rule and removes it when it ends; `modal app stop` skips
that cleanup, as it does for the fleet. Running it alongside a restarted pod is
safe: point inserts are `ON CONFLICT DO NOTHING`, and the direct-report sweep
row-locks its counters and watermark, so a concurrent sweep waits and continues
from the new mark.

DP weight is a Hamming-weight cutoff, not a different record size: both cutoffs
use the same 32-byte record. For two corpora with the **same walk identity**,
`dp_compat.py` can retain DP34 records whose endpoint already satisfies DP32,
preserving their seed and endpoint bytes. It rejects different walks, invalid
records, widening cutoffs and existing destinations. Supply the actual source
and target campaign configurations:

```sh
python3 ecc2k130/runner/dp_compat.py --input old-dp34.bin --output retained-dp32.bin \
  --source-config same-walk-dp34.json --target-config same-walk-dp32.json
```

This is endpoint filtering, not full trail conversion. Weight-34 endpoints
would need replay/continuation under the same walk to reach DP32. For the table
walk, replay must also recover the cycle-history state. Relabeling a table-walk
configuration as Frobenius does not convert its records.

`maxIters` restarts a walk that has gone that many steps without a report, and
the restarted walk's steps are lost, so the limit belongs far out in the tail of
the trail length. At DP32 a trail averages 2^28.41 steps: the former 2^30 (three
mean trails) cut 4.9% of honest trails and discarded 15.6% of all steps, while
the template's 2^32 cuts 0.0006%
([crypto WALK-CONSTANT.md §6](https://github.com/aburan28/crypto/blob/main/ecc2k130/WALK-CONSTANT.md)).
The Frobenius walk has no fruitless cycles for the limit to catch. The limit
changes neither the walk nor the DP rule, and checkpoints do not store it, so
records and checkpoints stay compatible across a change. Workers read the S3
copy of `campaign.json`, which `run` never overwrites, and load it once per
worker process. To change a live campaign, edit only `maxIters` in that copy;
workers use it from their next start:

```sh
key="s3://$ECC_BUCKET/$ECC_PREFIX/campaign.json"
aws s3 cp "$key" campaign.json
python3 -c 'import json; c = json.load(open("campaign.json")); c["maxIters"] = 1 << 32; json.dump(c, open("campaign.json", "w"), indent=2)'
aws s3 cp campaign.json "$key"
```

The measured compatibility experiment and cutoff calculations are documented in
[research/DP-RECONCILIATION.md](research/DP-RECONCILIATION.md). Run
`modal run ecc2k130/runner/reconcile_dp.py` to compare the legacy, production and faster
profiles with identical DP32 workloads, then check the best compatible profile's
checkpoint exchange and five paired timing repetitions. The experiment uses one
temporary GPU and reads the pinned legacy binary from S3; its records stay in
temporary storage.

Extra client arguments cannot override the leased run ID or persistence paths.
Checkpoint creation and the upload schedule use 60-second intervals. Uploads
can take longer depending on the network and database; the next periodic upload
is scheduled 60 seconds after completion. Checkpoints are acknowledged only
after both S3 and RDS reporting succeed.

The container includes the AWS RDS CA bundle and sets `PGSSLROOTCERT` to its
container path, so the database connection can use `sslmode=verify-full`.
`RHO_DP_DSN` can omit the password when `PGPASSWORD` is supplied separately
through the provider secret. Do not forward a laptop-specific `PGSSLROOTCERT`
path to the container.

RDS must be reachable from the provider, with appropriate routing, firewall
rules and TLS configuration. A private RDS endpoint needs an existing network
path. A DSN alone cannot make a private database reachable.

## Modal

Install/authenticate the Modal CLI and create a Modal secret named
`ecc2k130-cloud` containing the environment variables above. Set `ECC_MODAL_SECRET`
to use a different secret name. Each worker uses one RTX PRO 6000 GPU. This
certified build requires CUDA architecture 120 and CUDA 13.3.1; the Dockerfile
rejects a different architecture. Other GPU types require a separately validated
build and compatible campaign configuration.

Each GPU worker requests two CPU cores. Modal bills the larger of the request
and actual use. Live workers averaged 1.16 cores (90th percentile 1.58, peak
2.82): the client spins one core while waiting for the GPU, and uploads briefly
add more. The earlier four-core request left about 2.8 paid cores idle.
Releasing them saves about 3% of each worker's cost. Filling them with the CPU
walker instead would add an estimated 0.2–0.4% throughput, at 15–25 M
iterations/s per core. At that rate, paid Modal cores yield 10–17 times fewer
iterations per dollar than RTX PRO 6000 time. The client keeps four OpenMP
threads because the GPU idles while it converts each checkpoint.

The secret must exist before the first launch; creating a Modal app does not
create it. From the repository root, copy the template and fill in the real values
locally (the `.env` file is ignored by git and excluded from Docker builds):

```sh
cp ecc2k130/runner/.env.example ecc2k130/runner/.env
# Edit ecc2k130/runner/.env before running the next command.
modal secret create --env main ecc2k130-cloud --from-dotenv ecc2k130/runner/.env
```

Alternatively, create a custom secret with these keys in the Modal dashboard.
`modal secret list --env main` lists names without revealing values. If you use a
different Modal environment, select it consistently for secret creation and runs.
A `Secret 'ecc2k130-cloud' not found` error means this setup step is incomplete
or the run selected a different environment.

From the repository root (with `main` selected as the Modal environment):

```sh
# Optional for public RDS restricted to an IP allow-list. Use its security group.
# Requires EC2 describe/authorize/revoke security-group-rule permissions.
export ECC_RDS_SECURITY_GROUP=YOUR_RDS_SECURITY_GROUP

# Read configuration and check database schema visibility.
modal run ecc2k130/runner/modal_worker.py --command preflight

# Small S3/RDS round trip, without starting the GPU client.
modal run ecc2k130/runner/modal_worker.py --command smoke

# Four concurrent workers, each collecting for 23 hours.
modal run --detach ecc2k130/runner/modal_worker.py --command run --count 4 --seconds 82800

# A larger fleet: raise the per-app cap, then ask for that many workers.
ECC_MODAL_MAX_WORKERS=8 modal run --detach ecc2k130/runner/modal_worker.py --command run --count 8 --seconds 82800
```

`preflight` and `smoke` execute in a CPU container. Image construction may still
build the shared CUDA image, but these checks do not start GPU workers. `run`
first requires a successful S3/RDS smoke check, then submits every GPU call
before waiting for any result. `--count` accepts 1 through `ECC_MODAL_MAX_WORKERS`
(default 4, at most 32), which is also the app's cap on concurrent GPU containers.
Each worker adds one `/32` rule to the RDS security group, and AWS allows 60
inbound rules per group by default. Launch one app per fleet rather than several
copies, so the whole fleet shares one rollout, deadline and cleanup. Modal
retries a failed worker up to three times. A heartbeat whose conditional S3 write
conflicts with its own retried request re-reads the lease rather than give it up.
The launcher spawns a remote CPU coordinator, which prints the submitted call IDs
and waits for the workers. After a detached launch, closing the local terminal
ends neither the fleet nor the coordinator's network cleanup. The coordinator is
spawned because Modal cancels a `.remote()` call about a minute after its
launcher disconnects; the workers would keep running with their ingress rules
left open.
Submission is not proof of startup,
so check the logs for four distinct claimed slots and progress reports.

The GPU workers use the same Dockerfile as Runpod. Re-running `run` claims
available slots and resumes from S3; no Modal Volume is required. Each invocation
is bounded to 23 hours, below the 24-hour function timeout. All workers share one
absolute rollout deadline: Modal restarts a preempted call with its original
arguments, and the restarted worker runs only for the remaining time. The
coordinator therefore outlives every worker and removes the rollout's ingress
rules. This is one bounded
fleet run (up to 92 GPU-hours), not an automatically renewing daily deployment. Shutdown still
requires the provider to allow enough time to finish the current kernel and
upload. An abrupt termination recovers from the last acknowledged checkpoint.
See the official [Modal image reference](https://modal.com/docs/reference/modal.Image)
for Dockerfile build contexts and [secret guide](https://modal.com/docs/guide/secrets)
for environment injection.

With `ECC_RDS_SECURITY_GROUP` set, each Modal worker adds only its actual public
IPv4 `/32` on TCP 5432. The coordinator removes rules tagged for its rollout when
all workers finish; existing administrator rules are never adopted or deleted.
Hard cancellation of the app can bypass cleanup: inspect descriptions beginning
`ecc2k130-rollout-` and remove only rules belonging to the stopped rollout.
`modal app stop` is such a cancellation. It terminates the containers
immediately, so the workers cannot write a final checkpoint. They resume from
their last upload, which was 8–136 seconds old in the 2026-09-25 stop. Wait for the 180-second slot
leases to expire before relaunching; otherwise new workers allocate fresh slots
instead of resuming the stopped ones. Leave
this setting unset when an existing network path or static egress allow-list
already provides access. Runpod uses its configured network path; the Modal
coordinator's managed ingress is not part of the standalone Docker command.

The older `modal_app.py` remains available for engine validation, tuning and
Modal Volume experiments. Its `search`/`fanout` commands **do not use the new
S3/RDS worker**. Likewise `run.sh` is the older Volume-based experiment launcher.

## Runpod (GPU Pod)

Build an amd64 image and publish it to a registry you use with Runpod:

```sh
docker build --platform linux/amd64 \
  -f ecc2k130/runner/deploy/Dockerfile --build-arg CUDA_ARCH=120 \
  -t YOUR_REGISTRY/ecc2k130:runner ecc2k130/runner
docker push YOUR_REGISTRY/ecc2k130:runner
```

Choose that custom image in a Runpod **Pod**, select an RTX PRO 6000 Blackwell
Server Edition, and set the
environment variables above. Set the container start command to one of:

```sh
python3 /opt/ecc2k130/cloud.py preflight
python3 /opt/ecc2k130/cloud.py smoke
python3 /opt/ecc2k130/cloud.py run --seconds 3600
```

The image's default command runs for 23 hours. It does not create another Pod
or restart itself after that duration. Stop the billable Pod when finished.
One worker drives one GPU; start with a one-GPU Pod. If running multiple workers
in one container, give each its own `ECC_GPU` index. S3 leases provide different
run IDs. Mount persistent storage at `/workspace` if desired; S3 remains the
cross-provider recovery source. See Runpod's
[custom Docker image guide](https://www.runpod.io/articles/guides/deploying-models-with-docker-containers).

## Persistence and failure behavior

* Records are 32 bytes: an eight-byte starting seed and a 24-byte orbit key.
  Partial trailing records are held until complete. Delta copying and RDS
  reporting stream data with bounded memory. RDS calls are pipelined in batches
  of 256, avoiding one network round trip per point.
* The supervisor snapshots the checkpoint before reading new points, uploads
  the delta to S3, reports its records to RDS, and only then advances its local
  offset and publishes the checkpoint. An RDS failure leaves the delta pending
  for retry. Final upload failure returns a nonzero exit status.
* Delivery is at least once. Database reporting must deduplicate the same
  campaign, point key and seed. S3 keys include a content digest, preventing
  retries or file rotations from overwriting a different delta.
* Slot owners are unique per process. RDS reporting renews the lease during
  long deltas. An uncertain/lost lease stops publication and shuts down the
  client. A replacement may replay work after the last persisted checkpoint.
* The fixed lease is 180 seconds. Individual blocking cloud operations must
  complete within that lease window; large checkpoint transfers and real RDS
  ingestion throughput still need measurement on the chosen provider/network.
* A checkpoint rejected by the client retires that slot. Changing build geometry
  does not silently restart its seed range.

`smoke` writes one 32-byte S3 object under a unique `checks/` key, reads it back,
then tests a new point, duplicate, and collision in an isolated RDS campaign
inside a transaction that is rolled back. No test campaign/DP rows remain;
PostgreSQL sequence counters may advance. The S3 object remains for diagnosis;
a lifecycle rule on `checks/` can expire it. The command does not claim a worker
slot or launch the client.

## Local verification

```sh
make -C ecc2k130/runner check-cloud
make -C ecc2k130/runner check-cli
make -C ecc2k130/runner cpu
./ecc2k130/runner/ecc2k130-cpu --test
env -u DATABASE_URL -u RHO_DP_DSN bash ecc2k130/runner/aws/rehearse_worker.sh
```

On macOS, use Homebrew GCC for OpenMP:

```sh
make -C ecc2k130/runner cpu \
  CXX="/opt/homebrew/bin/g++-16 -isysroot $(xcrun --show-sdk-path)"
```

The worker rehearsal uses a local directory in place of S3 and the real CPU
client on small curves. It checks exact uploaded bytes, same-slot restart,
recovery on a fresh worker, and solution persistence. The cloud unit tests inject
storage/DB failures and check publication ordering, retry, checkpoint snapshots,
lease loss, and immutable delta names. They do not prove live cloud connectivity.

**Production compatibility validation:** [the exact-image GPU receipt](research/production/2026-09-21-120k-deployment-validation.json)
compares the deployed build with the SHA-256-pinned legacy binary named by the
shared S3 campaign. All six fresh/checkpoint/resume cases matched, including
10,249 successful host-reference report verifications. At the production
population, the build reproduced the original 355-record DP32 screening corpus.
The [deployment receipt](research/production/2026-09-21-120k-deployment.json)
records the canary and four live workers; it is not a completed 23-hour soak.
Re-run the binary checks with `modal run ecc2k130/runner/deployment_validate.py`
from the repository root. Inspect live leases, checkpoints and indexed RDS
sample records with `modal run ecc2k130/runner/verify_production.py` (set
`ECC_RDS_SECURITY_GROUP` if managed temporary RDS access is needed).

**Table-walk research validation (superseded production profile):** its timing, replay, corpus, and checkpoint
evidence is in [research/candidates/goal22/](research/candidates/goal22/).
The production CUDA image built on Modal; its CPU smoke check passed the S3
byte round trip and transactional RDS new/duplicate/collision checks. A bounded
GPU run persisted 139,414 records with zero drops, exited cleanly, and released
its lease. The next fleet resumed that checkpoint in a fresh container.
Four RTX PRO 6000 workers subsequently ran at roughly 21.0–21.5 billion
updates/sec each; all four published S3 deltas/checkpoints and real RDS records.
This establishes launch and persistence, not a completed 23-hour soak test.
The launch receipt is [research/production/2026-09-21-modal-rollout.json](research/production/2026-09-21-modal-rollout.json).

Local validation passed 38 cloud tests, 102 CLI/report tests, CPU engine checks,
and the shutdown/resume/solution rehearsal. Seven CLI tests were skipped:
four for the excluded EC2 benchmark provisioner and three requiring optional
SAT dependencies. Runpod execution remains unverified. No ingester or other
dedicated service is required. The arithmetic acceptance receipt also records
the unavailable Compute Sanitizer and inherited `test-clmad` test limitations;
those checks are not claimed as passing.
