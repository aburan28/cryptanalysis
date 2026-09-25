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

The 2026-09-25 rollout resumes runs 12,000–12,003 from their S3 checkpoints on
four RTX PRO 6000 workers in
[Modal app ap-0QctCWSXDTzBSyBYcjVM3i](https://modal.com/apps/a-buran28/main/ap-0QctCWSXDTzBSyBYcjVM3i),
until 2026-09-26 02:47 UTC. It is the first rollout of the fused Frobenius build
(profile v2). That exact image passed the legacy compatibility gate in
[its validation receipt](research/production/2026-09-25-fused-deployment-validation.json).
At startup the four clients reported 70.08 billion updates/s in total, zero
drops, advancing checkpoints and matching RDS samples. See the
[deployment receipt](research/production/2026-09-25-fused-deployment.json).

The 2026-09-21 rollout ran four RTX PRO 6000 workers in
[Modal app ap-89OUG2uEQpkkKtdd1WO8ru](https://modal.com/apps/a-buran28/main/ap-89OUG2uEQpkkKtdd1WO8ru).
Run 12,000 resumed the successful three-minute canary; runs 12,001–12,003 started
fresh. The older volume-backed jobs were stopped gracefully, with their final
checkpoints and 71,194,498 stored DP records verified in the persistent volume.
See the [deployment receipt](research/production/2026-09-21-120k-deployment.json)
for runtime identities, validation and live storage/database checks.

The existing [public crypto dashboard](https://aburan28.github.io/crypto/status/)
currently reports `ecc2k-130` at DP weight **32**. It reads root-level `ckpt/`
objects and the legacy ingester's RDS counters. This fleet shares its actual
collision table, but the page still needs support for namespaced checkpoints
and direct reporting to account for this fleet's contribution accurately.
Its "GPUs running" count means a checkpoint was uploaded within 30 minutes;
copying an old checkpoint can refresh that timestamp after a worker stops.
Use the Modal app's worker logs and this campaign's S3 leases/RDS rows to check
the new fleet. Archived `ecc2k130-table8-22b-v1` records have a different walk
identity and must remain separate; they are not relabeled or merged by this
production switch.

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
```

`preflight` and `smoke` execute in a CPU container. Image construction may still
build the shared CUDA image, but these checks do not start GPU workers. `run`
first requires a successful S3/RDS smoke check, then submits all four GPU calls
before waiting for any result. `--count` accepts 1 through 4 (default 4), and the
GPU function has a maximum of four concurrent containers per app. Avoid launching
multiple copies of the app if you intend to keep the total fleet at four GPUs.
The remote CPU coordinator prints the submitted call IDs and waits for completion,
so closing the local terminal after a detached launch does not end the fleet.
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
`ecc2k130-rollout-` and remove only rules belonging to the stopped rollout. Leave
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
