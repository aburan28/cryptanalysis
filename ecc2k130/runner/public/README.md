# ECC2K-130 contributor network

This package lets invited contributors run the **legacy Frobenius sigma walk at
DP32** on NVIDIA GPUs and deliver its 32-byte distinguished-point records to
the existing `ecc2k-130` collision pool. The contributor image receives a
public HTTPS URL and a join token. AWS credentials and the RDS connection stay
on the gateway host. It uses the public `ec2k-gpu` client and its campaign
known-answer file; the managed fleet continues to use
[`runner/cloud.py`](../cloud.py) and its separate checkpoint format.

```text
NVIDIA GPU + persistent /data  --HTTPS-->  gateway + durable /data
       sigma walk                         |  run ID reserved in shared S3 registry
       DP file + checkpoint               |  immutable raw DP batches, checkpoints
                                         +--> ingester --> existing RDS report_dp
                                                              | collision receipts
```

The gateway checks the assigned run ID, record length, orbit-key bit width,
and DP32 cutoff. These structural checks do **not** prove that a submitted
point comes from the claimed seed. Raw files and any RDS collision receipt
must be retained for independent seed replay before claiming a result. The
join token should be given to identified contributors; an anonymous open
upload endpoint would allow false points to pollute the shared table.

## Build

From the `cryptanalysis` repository root, with a working Docker daemon:

```sh
python3 ecc2k130/runner/public/build_images.py worker --tag ecc2k130-worker:local
python3 ecc2k130/runner/public/build_images.py gateway --tag ecc2k130-gateway:local
python3 -m unittest ecc2k130/runner/public/test_public.py -v
```

The build script stages only the named source files into a temporary context.
The worker build compiles the sigma walk for `sm_80`, `sm_86`, `sm_89`,
`sm_90`, `sm_100`, and `sm_120`, includes `compute_120` PTX, runs host tests,
and checks the campaign known answers. A GPU device run and report re-walk
are still required on each claimed hardware class. The CI tag workflow builds
and publishes Linux amd64 images to GHCR; the digest from that workflow is
the image identity to distribute.

## Gateway deployment

Run this on a host with public DNS, TCP 80/443, a persistent Docker volume,
access to the campaign S3 bucket's **existing** seed registry, and RDS network
reachability for the ingester. The bucket's
`seed-registry/curve-131/config.json` must already say `state: ready`.
The gateway uses S3 conditional `PutObject` on
`seed-registry/curve-131/run-*.json` before handing out any run ID. Its IAM
role needs only `GetObject` for the registry configuration and `PutObject` for
the run records; a combined ingester host also reads the RDS secret. Keep
`ECC_PUBLIC_STREAM_ID` stable across redeployments.

[`deploy/aws-gateway.yaml`](deploy/aws-gateway.yaml) is the reviewable AWS
rollout template. It creates a `t3.medium` EC2 instance with a 100 GiB
encrypted EBS volume, an Elastic IP, inbound TCP 80/443 and UDP 443, a
generated join token in Secrets Manager, and a scoped EC2 role. It builds
the gateway from an exact merged source commit and starts only the gateway
and HTTPS ingress. Its public address uses the IP-derived `sslip.io` DNS
service until a project-owned domain is configured; that external DNS
dependency must be checked during rollout. The EC2 role also has read access
to the existing `rho/dp-rds` secret for the separate ingester. It has no
general bucket write permission. The template is not applied by a build or
PR check.

After reviewing the template, selecting a public subnet, and recording the
source commit, a deployment uses `aws cloudformation deploy` with
`CAPABILITY_IAM` and parameters `SourceCommit`, `VpcId`, and `SubnetId`.
The source commit is a 40-character SHA reachable on `main`; the stack
outputs the HTTPS URL, instance ID, and join-secret ARN. Preserve the EBS
volume and retained join secret when replacing or removing the stack.
Inspect cloud-init logs, `docker compose ps`, public `/health`, certificate
validation, and one S3 run-ID reservation before sharing the URL.

Audit the proposed run-ID interval against the shared registry and every
historical owner using the canonical
[`crypto/ecc2k130/aws/seed_audit.py`](https://github.com/aburan28/crypto/blob/main/ecc2k130/aws/seed_audit.py)
procedure. The gateway skips occupied IDs through a conditional S3 write.
This does not protect against old unguarded clients: check that no such client
can use the interval. Never reset the SQLite volume, reuse the stream ID for a
different campaign, or restart a used ID from iteration zero.

Create `.env` beside `compose.yaml` on the gateway host (do not commit it):

```sh
ECC_PUBLIC_HOST=ecc2k130.example.org
ECC_GATEWAY_IMAGE=ghcr.io/aburan28/ecc2k130-gateway@sha256:REVIEWED_DIGEST
ECC_PUBLIC_JOIN_TOKEN=GENERATE_A_LONG_RANDOM_TOKEN
ECC_PUBLIC_STREAM_ID=stable-public-gateway-v1
ECC_BUCKET=YOUR_EXISTING_CAMPAIGN_BUCKET
AWS_DEFAULT_REGION=us-west-2
ECC_RUN_ID_START=VERIFIED_FIRST_UNUSED_ID
ECC_RUN_ID_END=VERIFIED_LAST_UNUSED_ID
# Set RHO_DP_DSN through deploy/enable_ingest.py after the gateway check.
```

Give the gateway an IAM instance role instead of placing AWS keys in `.env`.
`RHO_DP_DSN` is needed only for the `live-ingest` profile and is passed only
to that container. Back up the `state`
volume: it contains contributor tokens, raw records, checkpoint snapshots,
RDS ingestion cursors, and collision receipts. The local Docker volume is the
durable source for a contributor upload. Monitor its free space and back it up
off-host before inviting a large fleet.

```sh
cd ecc2k130/runner/public
docker compose up -d gateway ingress
curl --fail https://ecc2k130.example.org/health
# After a controlled end-to-end upload and RDS contract check:
python3 deploy/enable_ingest.py \
  --db-host rho-dp.cxqyicswioh8.us-west-2.rds.amazonaws.com --start
```

`enable_ingest.py` reads the existing `rho/dp-rds` secret without printing it,
downloads the AWS RDS CA bundle, writes a mode-0600 DSN into `.env`, checks
the existing campaign row over verified TLS without a DP write, and then
starts the ingester if `--start` was given. The local CA bundle is ignored by
Git. The first real upload still needs an RDS sample lookup and independent
seed replay when a collision is recorded.

The gateway must use the existing campaign row and its `report_dp` function;
the ingester validates that metadata before writing. A database failure leaves
accepted raw batches pending. `GET /health` reports the pending count. The
ingester labels its writes `public-run-ID:unverified` and records possible
collisions in `collision_records`; a collision is a replay task, not a solved
scalar. A separate resolver from the campaign's `crypto` source must perform
seed re-walk and coefficient recovery.

## Contributor command

On Linux amd64 with an NVIDIA driver supporting CUDA 13.3 and a GPU at
`sm_80` or newer, give each GPU its own persistent host directory:

```sh
docker run -d --name ecc2k130-gpu0 --restart unless-stopped \
  --gpus '"device=0"' --stop-timeout 600 \
  -e ECC_API_URL=https://ecc2k130.example.org \
  -e ECC_JOIN_TOKEN=TOKEN_FROM_CAMPAIGN_OPERATOR \
  -v "$PWD/ecc2k130-gpu0:/data" \
  ghcr.io/aburan28/ecc2k130-worker@sha256:REVIEWED_DIGEST
docker logs -f ecc2k130-gpu0
```

The worker obtains one permanent run ID, saves the bearer token in
`/data/state.json` with mode 0600, checks the CPU known answers, and starts
the GPU walk. It uploads only complete DP records, retries the same bytes at
the same offset, then sends a checkpoint. SIGTERM gives the CUDA client time
to flush and triggers a final upload. A new container with the same `/data`
resumes its run. If local state is lost, keep the gateway's record and
checkpoint for recovery; do not delete the registry assignment or start that
ID again from zero. The join token is only needed at first registration.

The client requires HTTPS outside localhost. The gateway requires a join
token, uses per-run bearer tokens, bounds upload sizes, and never gives AWS
or RDS credentials to contributors. Invitation, rate limiting at ingress,
storage quota monitoring, and seed-replay review remain operator duties.

## Verification boundaries

Local tests cover registration, shared registry reservation, token checks,
DP offset replay, rejected malformed records, checkpoint transfer, raw batch
retention, and a mocked RDS collision receipt. They do not certify the image
on a GPU, the public hostname, S3 permissions, RDS routing, global throughput,
or an answer to the Certicom challenge. For a live rollout, retain the image
digest, source commit, seed-audit receipt, gateway and ingester logs, GPU
device check, one actual S3 registration, one accepted upload, an RDS sample
lookup, and independent replay of any collision.
