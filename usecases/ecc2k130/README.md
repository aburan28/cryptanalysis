# ECC2K-130: the first cryptanalysis use case

This directory connects the live Certicom ECC2K-130 run to this repository's
cryptanalysis tooling. It replaces the long-running process that repeatedly
listed the entire S3 `dp/` prefix with a durable Redis Streams handoff:

```text
walker
  ├─ immutable DP/checkpoint bytes ─▶ S3
  └─ object reference ─▶ Redis Stream ─▶ consumer group ─▶ RDS index
          ▲ red: retain spool + pause                       └▶ status.json
```

S3 is the corpus authority. RDS is a rebuildable query/collision index. The
stream contains only small object references and record counts—not raw DPs.
Replaying an entry is harmless. Consumers recover abandoned pending entries,
dead-letter deterministic poison messages, and atomically `XACK` + `XDEL`
only after the RDS transaction commits.

Use AWS MemoryDB with TLS, Multi-AZ durability and
`maxmemory-policy=noeviction`. Do **not** point `RHO_QUEUE_REDIS_URL` at the
existing fail-open ElastiCache used for disposable cache hints. A cache may
evict or disappear; this queue may not.

The supported production profile is `RHO_QUEUE_BACKEND=memorydb` with the
cluster-aware client. Startup refuses an unbounded instance or a policy other
than `noeviction`. `RHO_QUEUE_BACKEND=standalone` exists only for local tests;
it deliberately skips the service-level durability assertion.

There is still code that indexes each new object, but no polling ingest host
and no continuously running prefix scan.

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
| ready stream | `rho:{ecc2k-130}:dp:ready` |
| consumer group | `indexers` |
| pressure hash | `rho:{ecc2k-130}:dp:pressure` |
| queue counters | `rho:{ecc2k-130}:dp:stats` |
| dead-letter stream | `rho:{ecc2k-130}:dp:dead` |

The live campaign currently has legacy `campaign.json` metadata, so a
content-addressed `.bin` without a sidecar remains accepted when
`ECC2K130_CAMPAIGN_ID` is empty. Set that variable to the strict campaign
contract SHA-256 during the storage-protocol migration; from then on, a
matching `.bin.json` becomes mandatory.

Legacy `<epoch>-<offset>.bin` keys are intentionally not accepted by this
event path. They are historical and already indexed. A one-time migration
can replay them through the old importer, but new production writes must be
content-addressed.

Legacy mutable `ckpt/slot-NNNNN.ck` remains supported only when S3 bucket
versioning supplies a `VersionId`; that version is part of the queue and RDS
identity. New checkpoints should use immutable
`ckpt/slot-NNNNN/<sha256>.ck` keys.

## Correctness contract

1. A walker uploads a whole, immutable 32-byte-record payload.
2. S3 atomically creates the object. Its key contains the payload SHA-256.
3. The walker `XADD`s the object reference. It does not clear its local spool
   until Redis confirms that write.
4. A consumer verifies the S3 key hash, record boundaries, and strict sidecar
   when configured.
5. One RDS transaction writes points, collisions, rollups, the compatibility
   progress row, and `ecc2k130_commits`.
6. One Redis Lua operation acknowledges and deletes the stream entry and
   decrements queue byte/record counters only after that transaction commits.

Checkpoint references take the same queue. Their 40-byte header carries the
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

## Backpressure

`stream.py` publishes a durable pressure state from four independent signals:

- queue message count,
- queued payload bytes,
- age of the oldest unacknowledged object,
- Redis `used_memory / maxmemory`.

Each has a configurable yellow and red threshold. The `XADD` Lua script also
enforces the critical message/byte limits atomically, so a stale pressure hash
cannot race past the hard cap. `publish.py` exits with `EX_TEMPFAIL` (75) at
red. The worker must then retain the spool entry and retry; when its own spool
reaches its safety limit it pauses the client rather than dropping DPs.

One DP object is capped at `RHO_QUEUE_MAX_DP_BYTES` (8 MiB by default) before
the consumer can allocate it; checkpoint consumers fetch only the 40-byte
header for mutable versions and stream-hash immutable checkpoint bodies
without materializing them. Queue-byte pressure counts full DP payload bytes
and a fixed 40-byte checkpoint cost, with a separately configured
checkpoint-object limit.

Yellow is an operational warning and should trigger scale-out before red.
Red is flow control, not an error to bypass. Redis connection failures and
OOM errors are also fail-closed: the worker keeps its spool.

Do not use `MAXLEN ~` trimming on the ready stream; it can discard unprocessed
entries. Successful consumers atomically `XACK` + `XDEL`. Abandoned pending
entries are recovered with `XAUTOCLAIM`; deterministic poison records move to
the dead-letter stream after `RHO_QUEUE_MAX_DELIVERIES`. RDS/S3 outages stay
pending indefinitely and are never dead-lettered merely for being unavailable.
Dead-lettered object keys remain quarantined in the queued-object hash, so the
reconciler cannot create an infinite poison loop; an operator explicitly
removes that hash field when re-driving a repaired object.

## Deploy

Prerequisites: a durable Redis-compatible cluster reachable by walkers and
consumers, and a consumer runtime that can also reach S3, `rho-dp`, and
Secrets Manager. Use separate producer and consumer ACL users.

Walkers do not receive Redis credentials. `publish.py` calls the authenticated
internal service in `publish_api.py`; that service validates the configured
bucket with S3 `HeadObject`, derives bytes/records itself, and alone holds the
producer ACL. Its Redis command set is `EVALSHA`/`SCRIPT LOAD`, `INFO`, `TIME`,
`INCR`, `XLEN`, `XRANGE`, `XPENDING`, `HGET`, `HGETALL`, `HSET`, `HDEL`,
`HINCRBY`, `XADD`, and cluster discovery. The consumer additionally needs `XGROUP`, `XREADGROUP`,
`XAUTOCLAIM`, `XACK` and `XDEL`. Restrict both service users to
`~rho:{ecc2k-130}:dp:*`.

```sh
cd usecases/ecc2k130

# Apply once through a network path that can reach RDS.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql

# Build and run the stateless services in ECS, Kubernetes, or systemd.
docker build -t cryptanalysis-ecc2k130-index .
docker run --env-file /etc/ecc2k130-index.env cryptanalysis-ecc2k130-index
docker run --env-file /etc/ecc2k130-index.env \
  cryptanalysis-ecc2k130-index python publish_api.py
```

The worker hook runs only after both the S3 payload and optional strict sidecar
are durable:

```sh
python3 publish.py \
  --bucket ecc2k130-590183823895 \
  --key 'dp/slot-00140/<stream>-<offset>-<sha256>.bin'
```

Exit 0 lets the worker clear that spool entry. Exit 75 or any Redis error
means retain it and retry. The hook must not be best-effort.

S3 and Redis cannot share a transaction. A host can still disappear after S3
accepts bytes and before `XADD`. Schedule `reconcile.py` as a low-frequency
safety repair (for example, every ten minutes): it lists object keys only,
compares them with the RDS commit ledgers, and queues missing references
through the same pressure gate. It never reads or inserts DP bodies.

```sh
docker run --rm --env-file /etc/ecc2k130-index.env \
  cryptanalysis-ecc2k130-index python reconcile.py
```

The first reconciliation pass also backfills every immutable checkpoint and
every S3 version of a legacy mutable checkpoint; it queues references only and
does not rewrite the corpus.

### Cutover from `dp_ingest.py`

1. Apply the schema and deploy the queue consumer.
2. Roll out the mandatory worker publish hook; verify one object reaches the
   stream before its local spool is cleared.
3. Replay checkpoints, then run the old importer once to close the pre-hook
   DP gap.
4. Wait for ready-stream length and pending count to reach zero; inspect the
   dead-letter stream.
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

Deployment libraries are imported only inside their entry points, so the
protocol tests run without services. Set `ECC2K130_TEST_DATABASE_URL` and
`ECC2K130_TEST_REDIS_URL` to additionally run transactional indexing,
consumer-group ACK/recovery, dead-letter, hard-limit and backpressure tests.
CI runs those suites against PostgreSQL 16 and Redis 7.4.
