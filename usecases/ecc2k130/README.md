# ECC2K-130: the first cryptanalysis use case

This directory connects the live Certicom ECC2K-130 run to this repository's
cryptanalysis tooling. It replaces the long-running process that repeatedly
listed the entire S3 `dp/` prefix with an event-driven commit path:

```text
walker
  ├─ immutable .bin ─▶ S3 ─ ObjectCreated ─▶ SQS ─▶ Lambda ─▶ RDS index
  └─ checkpoint .ck ────────────────────────────────▶ work totals
                                                       └─────▶ status.json
```

S3 is the corpus authority. RDS is a rebuildable query/collision index. SQS
only delivers object notifications and has a dead-letter queue; replaying a
message is harmless. A scheduled invocation publishes the dashboard from
fixed-cost RDS aggregates every three minutes and never lists the corpus.

## Why SQS, not Redis

Redis Streams could carry the notification, but it would require every worker
to become a Redis producer and would still need reconciliation when a worker
uploaded to S3 but failed before `XADD`. S3 publishes directly to SQS, SQS
retains messages for 14 days, and Lambda natively retries failed records into
a DLQ. Redis remains useful as an optional fleet/cache layer; it is not a
durable corpus handoff or a second source of truth.

There is still code that *indexes* a new object. There is no polling ingest
host and no continuously running prefix scan.

## Live resource paths

These names identify resources, not credentials:

| Purpose | Path |
|---|---|
| campaign | `ecc2k-130` |
| region/account | `us-west-2` / `590183823895` |
| corpus | `s3://ecc2k130-590183823895/dp/` |
| strict payload | `dp/slot-NNNNN/<stream32>-<offset16>-<sha256>.bin` |
| optional strict marker | same key plus `.json` |
| checkpoints | `s3://ecc2k130-590183823895/ckpt/` |
| slot records | `s3://ecc2k130-590183823895/slots/` during legacy cutover |
| public feed | `s3://ecc2k130-status-590183823895/status.json` |
| RDS instance | `rho-dp` |
| RDS endpoint | `rho-dp.cxqyicswioh8.us-west-2.rds.amazonaws.com:5432` |
| database secret | Secrets Manager `rho/dp-rds` |

The live campaign currently has legacy `campaign.json` metadata, so a
content-addressed `.bin` without a sidecar remains accepted when
`ECC2K130_CAMPAIGN_ID` is empty. Set that variable to the strict campaign
contract SHA-256 during the storage-protocol migration; from then on, a
matching `.bin.json` becomes mandatory.

Legacy `<epoch>-<offset>.bin` keys are intentionally not accepted by this
event path. They are historical and already indexed. A one-time migration
can replay them through the old importer, but new production writes must be
content-addressed.

## Correctness contract

1. A walker uploads a whole, immutable 32-byte-record payload.
2. S3 atomically creates the object. Its key contains the payload SHA-256.
3. S3 emits at least one SQS message.
4. The Lambda verifies the key hash, record boundaries, and strict sidecar
   when configured.
5. One RDS transaction writes points, collisions, rollups, the compatibility
   progress row, and `ecc2k130_commits`.
6. The SQS message is acknowledged only after that transaction commits.

Checkpoint events take the same queue. Their 40-byte header carries the
iteration base and walk geometry, so `ecc2k130_checkpoints` can publish
cumulative work without listing `ckpt/`.

`ecc2k130_commits (campaign_id, object_key)` is the idempotency key. A retry
with the same hash returns `duplicate`; the same key with different bytes is
an error. A failed transaction leaves no commit row. The immutable S3 object
always remains available for replay and independent collision verification.

The packed record is the live campaign format:

```text
seed:u64-le | k0:u64-le | k1:u64-le | k2:u64-le
```

The point key is bytes 8..31 (the Frobenius/negation orbit representative).
The queue consumer preserves the existing `distinguished_points`,
`dp_ingest_*`, `rho_collisions`, and `rho_objects` tables so the public site
can move without a flag day.

## Deploy

Prerequisites: AWS SAM, a VPC subnet/security group that can reach `rho-dp`,
permission to deploy Lambda/SQS/IAM resources, and either NAT or VPC endpoints
for S3, SQS, and Secrets Manager from those subnets.

```sh
cd usecases/ecc2k130

# Apply once through a network path that can reach RDS.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql

sam build
sam deploy --guided
```

The stack outputs `QueueArn`. Add the notification without replacing unrelated
bucket notifications:

```sh
python3 configure_notification.py \
  --bucket ecc2k130-590183823895 \
  --queue-arn <QueueArn>
```

Backfill the latest checkpoint state once (this queues work; it does not scan
or rewrite the DP corpus):

```sh
python3 replay_checkpoints.py \
  --bucket ecc2k130-590183823895 \
  --queue-url <QueueUrl>
```

The queue policy restricts `SendMessage` to that bucket and AWS account. The
Lambda can read only `dp/*`, write only the public `status.json`, read the RDS
secret, and reach resources in the supplied VPC.

### Cutover from `dp_ingest.py`

1. Apply the schema and deploy the queue consumer.
2. Configure the S3 notification.
3. Replay checkpoints, then run the old importer once to close the
   pre-notification DP gap.
4. Wait until the SQS visible/in-flight counts are zero and the DLQ is empty.
5. Stop the old polling ingest host.
6. Confirm `generated_at` and cumulative work advance in public `status.json`.

Steps 2 and 3 may overlap because both writers are idempotent on the existing
point key and compatibility progress key. Do not delete the old progress
tables during cutover.

## Local tests

The unit tests require no AWS or Postgres:

```sh
python3 -m unittest discover -s usecases/ecc2k130/tests -v
```

`boto3` and `psycopg` are imported only inside the deployed entry points, so
the protocol and event tests run with the Python standard library. Set
`ECC2K130_TEST_DATABASE_URL` to additionally run the transactional
idempotency, collision, rollup, and checkpoint tests against PostgreSQL; CI
runs that suite against PostgreSQL 16.
