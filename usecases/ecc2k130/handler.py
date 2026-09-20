"""Event-driven ECC2K-130 corpus indexing.

Workers write immutable, content-addressed payloads to S3 and may write
``<payload>.json`` last as the strict campaign commit marker. Workers enqueue
the S3 object reference in a durable Redis Stream. This module verifies the
key, payload, and marker when the campaign has one, then updates the existing
RDS point index in one transaction.

S3 remains the corpus authority. Redis is durable delivery, and RDS is the
query/index view. Every operation is idempotent because the object key is
content-addressed and is also the database commit key.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import struct
import urllib.parse
from dataclasses import dataclass

PROTOCOL = "ecc2k-seed-orbit-v1"
RECORD_BYTES = 32
MAX_SLOT = 65534
MAX_DP_OBJECT_BYTES = 8 * 1024 * 1024
MAX_CHECKPOINT_OBJECT_BYTES = 16 * 1024**3
ORBIT_KEY_RE = re.compile(
    r"^dp/slot-(\d{5})/([0-9a-f]{32})-(\d{16})-([0-9a-f]{64})\.bin$"
)
CHECKPOINT_KEY_RE = re.compile(
    r"^ckpt/slot-(\d{5})(?:/([0-9a-f]{64}))?\.ck$"
)
CHECKPOINT_HEADER = struct.Struct("<8s6IQ")


@dataclass(frozen=True)
class Config:
    campaign: str
    campaign_id: str
    bucket: str
    status_bucket: str
    redis_url: str
    db_url: str
    db_host: str
    db_secret: str
    db_name: str
    db_sslmode: str

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env

        def get(name, default=""):
            return (env.get(name) or default).strip()

        return cls(
            campaign=get("RHO_CAMPAIGN", "ecc2k-130"),
            campaign_id=get("ECC2K130_CAMPAIGN_ID"),
            bucket=get("ECC_BUCKET"),
            status_bucket=get("ECC_STATUS_BUCKET"),
            redis_url=get("RHO_QUEUE_REDIS_URL"),
            db_url=get("DATABASE_URL"),
            db_host=get("RHO_DB_HOST"),
            db_secret=get("RHO_DB_SECRET", "rho/dp-rds"),
            db_name=get("RHO_DB_NAME"),
            db_sslmode=get("RHO_DB_SSLMODE", "require"),
        )

    def validate(self):
        if not self.bucket:
            raise ValueError("ECC_BUCKET is required")
        if not self.status_bucket:
            raise ValueError("ECC_STATUS_BUCKET is required")
        if not self.redis_url:
            raise ValueError("RHO_QUEUE_REDIS_URL is required")
        if not self.db_url and not self.db_host:
            raise ValueError("set DATABASE_URL, or RHO_DB_HOST plus RHO_DB_SECRET")


@dataclass(frozen=True)
class ObjectKey:
    key: str
    slot: int
    stream_id: str
    offset: int
    sha256: str


@dataclass(frozen=True)
class Point:
    point_key: bytes
    a: bytes
    b: bytes
    walk_seed: bytes


@dataclass(frozen=True)
class Batch:
    bucket: str
    object_key: ObjectKey
    manifest_key: str
    sha256: str
    body: bytes
    records: tuple[Point, ...]
    produced_at: dt.datetime


@dataclass(frozen=True)
class Checkpoint:
    bucket: str
    object_key: str
    version_id: str
    slot: int
    sha256: str
    iteration_base: int
    walks: int
    iterations: int
    produced_at: dt.datetime


def parse_object_key(key):
    """Parse one strict payload key; legacy uncommitted keys are rejected."""
    match = ORBIT_KEY_RE.fullmatch(key)
    if not match:
        raise ValueError(f"not an ECC2K-130 strict DP object: {key}")
    slot = int(match.group(1))
    if slot > MAX_SLOT:
        raise ValueError(f"slot {slot} exceeds the 16-bit run-id space")
    return ObjectKey(
        key=key,
        slot=slot,
        stream_id=match.group(2),
        offset=int(match.group(3)),
        sha256=match.group(4),
    )


def decode_records(body):
    """Decode packed ``(seed, k0, k1, k2)`` little-endian records."""
    if not body or len(body) % RECORD_BYTES:
        raise ValueError("DP payload must contain whole non-empty 32-byte records")
    points = []
    for off in range(0, len(body), RECORD_BYTES):
        record = body[off : off + RECORD_BYTES]
        seed, _, _, _ = struct.unpack("<QQQQ", record)
        points.append(
            Point(
                point_key=record[8:],
                a=seed.to_bytes(17, "big"),
                b=bytes(17),
                walk_seed=seed.to_bytes(8, "big").lstrip(b"\0") or b"\0",
            )
        )
    return tuple(points)


def _read_body(response):
    body = response["Body"]
    return body.read() if hasattr(body, "read") else bytes(body)


def _json_object(blob, name):
    try:
        value = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{name} must contain a JSON object")
    return value


def _timestamp(value, fallback=None):
    if isinstance(value, int) and value > 0:
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    if fallback:
        try:
            return dt.datetime.fromisoformat(str(fallback).replace("Z", "+00:00"))
        except ValueError:
            pass
    return dt.datetime.now(tz=dt.timezone.utc)


def _not_found(exc):
    response = getattr(exc, "response", None) or {}
    code = str((response.get("Error") or {}).get("Code") or "")
    return code in ("404", "NoSuchKey", "NotFound") or isinstance(exc, KeyError)


def load_batch(s3, config, bucket, notified_key, event_time=None):
    """Fetch and verify one immutable payload and its marker when required."""
    if bucket != config.bucket:
        raise ValueError(f"event bucket {bucket!r} does not match ECC_BUCKET")
    if notified_key.endswith(".bin.json"):
        payload_key = notified_key[: -len(".json")]
    elif notified_key.endswith(".bin"):
        payload_key = notified_key
    else:
        raise ValueError("only .bin payloads or .bin.json markers may enqueue work")
    manifest_key = payload_key + ".json"
    parsed = parse_object_key(payload_key)
    manifest = None
    try:
        manifest = _json_object(
            _read_body(s3.get_object(Bucket=bucket, Key=manifest_key)), manifest_key
        )
    except Exception as exc:
        if not _not_found(exc):
            raise
        # The live campaign predates strict envelopes. Its content-addressed
        # object key is still enough to detect truncation/corruption. Once a
        # campaign id is configured, the envelope becomes mandatory.
        if config.campaign_id:
            raise ValueError(f"{payload_key} is missing its campaign commit marker")
    response = s3.get_object(Bucket=bucket, Key=payload_key)
    content_length = int(response.get("ContentLength") or 0)
    if content_length > MAX_DP_OBJECT_BYTES:
        raise ValueError(
            f"{payload_key}: payload exceeds {MAX_DP_OBJECT_BYTES} byte limit"
        )
    body = _read_body(response)
    if len(body) > MAX_DP_OBJECT_BYTES:
        raise ValueError(
            f"{payload_key}: payload exceeds {MAX_DP_OBJECT_BYTES} byte limit"
        )
    digest = hashlib.sha256(body).hexdigest()

    if manifest is not None:
        expected = {
            "protocol": PROTOCOL,
            "kind": "dp",
            "bytes": len(body),
            "records": len(body) // RECORD_BYTES,
            "sha256": digest,
        }
        for field, want in expected.items():
            if manifest.get(field) != want:
                raise ValueError(
                    f"{payload_key}: manifest {field} is {manifest.get(field)!r}, expected {want!r}"
                )
    if digest != parsed.sha256:
        raise ValueError(f"{payload_key}: key hash does not match payload")
    if config.campaign_id and manifest.get("campaignId") != config.campaign_id:
        raise ValueError(f"{payload_key} belongs to another campaign")

    records = decode_records(body)
    if manifest is not None and len(records) != manifest["records"]:
        raise ValueError(f"{payload_key}: decoded record count mismatch")
    return Batch(
        bucket=bucket,
        object_key=parsed,
        manifest_key=manifest_key,
        sha256=digest,
        body=body,
        records=records,
        produced_at=_timestamp(
            manifest.get("producedAt") if manifest is not None else None, event_time
        ),
    )


def load_checkpoint(s3, config, bucket, key, event_time=None, version_id=""):
    """Read enough checkpoint state to publish cumulative campaign work."""
    if bucket != config.bucket:
        raise ValueError(f"event bucket {bucket!r} does not match ECC_BUCKET")
    match = CHECKPOINT_KEY_RE.fullmatch(key)
    if not match:
        raise ValueError(f"not an ECC2K-130 checkpoint object: {key}")
    slot = int(match.group(1))
    if slot > MAX_SLOT:
        raise ValueError(f"slot {slot} exceeds the 16-bit run-id space")
    if match.group(2) is None and (not version_id or version_id == "null"):
        raise ValueError("mutable checkpoint keys require an S3 VersionId")
    if match.group(2) is not None:
        version_id = ""
    request = {"Bucket": bucket, "Key": key}
    if version_id:
        request["VersionId"] = version_id
    if match.group(2) is not None:
        response = s3.get_object(**request)
        content_length = int(response.get("ContentLength") or 0)
        if content_length > MAX_CHECKPOINT_OBJECT_BYTES:
            raise ValueError(
                f"{key}: checkpoint exceeds {MAX_CHECKPOINT_OBJECT_BYTES} byte limit"
            )
        source = response["Body"]
        chunks = (
            source.iter_chunks(chunk_size=1024 * 1024)
            if hasattr(source, "iter_chunks")
            else iter(lambda: source.read(1024 * 1024), b"")
        )
        hasher = hashlib.sha256()
        header = bytearray()
        total = 0
        for chunk in chunks:
            if not chunk:
                continue
            hasher.update(chunk)
            total += len(chunk)
            if len(header) < CHECKPOINT_HEADER.size:
                need = CHECKPOINT_HEADER.size - len(header)
                header.extend(chunk[:need])
        body = bytes(header)
        digest = hasher.hexdigest()
        if digest != match.group(2):
            raise ValueError(f"{key}: checkpoint key hash does not match payload")
        if content_length and total != content_length:
            raise ValueError(f"{key}: checkpoint body is truncated")
    else:
        request["Range"] = f"bytes=0-{CHECKPOINT_HEADER.size - 1}"
        body = _read_body(s3.get_object(**request))
        digest = hashlib.sha256(body).hexdigest()
    if len(body) != CHECKPOINT_HEADER.size:
        raise ValueError(f"{key}: checkpoint header is truncated")
    magic, version, curve, threads, batch, lanes, run_id, iteration_base = (
        CHECKPOINT_HEADER.unpack_from(body)
    )
    if magic != b"ECC2K130" or version not in (1, 2) or curve != 131:
        raise ValueError(f"{key}: incompatible checkpoint header")
    if run_id != slot + 1:
        raise ValueError(f"{key}: run id {run_id} does not match slot {slot}")
    if not threads or not batch or not lanes:
        raise ValueError(f"{key}: invalid zero walk geometry")
    walks = int(threads) * int(batch) * int(lanes)
    iterations = int(iteration_base) * walks
    if walks > 2**63 - 1 or int(iteration_base) > 2**63 - 1:
        raise ValueError(f"{key}: checkpoint counters exceed bigint")
    if iterations >= 10**40:
        raise ValueError(f"{key}: checkpoint work exceeds numeric(40)")
    return Checkpoint(
        bucket=bucket,
        object_key=key,
        version_id=version_id,
        slot=slot,
        sha256=digest,
        iteration_base=int(iteration_base),
        walks=walks,
        iterations=iterations,
        produced_at=_timestamp(None, event_time),
    )


def _event_jobs(payload):
    """Yield ``(bucket, object key, event time)`` from S3/EventBridge JSON."""
    if not isinstance(payload, dict):
        raise TypeError("queue body must contain a JSON object")
    if payload.get("Event") == "s3:TestEvent":
        return

    # Native S3 notification remains accepted for migration/replay tooling.
    if isinstance(payload.get("Records"), list):
        for record in payload["Records"]:
            if record.get("eventSource") != "aws:s3":
                continue
            bucket = record.get("s3", {}).get("bucket", {}).get("name")
            key = record.get("s3", {}).get("object", {}).get("key")
            if not bucket or not key:
                raise ValueError("malformed S3 notification")
            key = urllib.parse.unquote_plus(key)
            if key.endswith((".bin", ".bin.json", ".ck")):
                yield (
                    bucket,
                    key,
                    record.get("eventTime"),
                    record.get("s3", {}).get("object", {}).get("versionId") or "",
                )
        return

    # EventBridge S3 Object Created event.
    detail = payload.get("detail")
    if isinstance(detail, dict):
        bucket = detail.get("bucket", {}).get("name")
        key = detail.get("object", {}).get("key")
        if bucket and key and key.endswith((".bin", ".bin.json", ".ck")):
            yield (
                bucket,
                urllib.parse.unquote_plus(key),
                payload.get("time"),
                detail.get("object", {}).get("version-id") or "",
            )
        return

    # Explicit message accepted for replay and operator recovery.
    if payload.get("bucket") and payload.get("manifestKey"):
        key = urllib.parse.unquote_plus(str(payload["manifestKey"]))
        if not key.endswith((".bin", ".bin.json", ".ck")):
            raise ValueError("manifestKey must end in .bin, .bin.json, or .ck")
        yield (
            str(payload["bucket"]),
            key,
            payload.get("eventTime"),
            str(payload.get("versionId") or ""),
        )
        return

    raise ValueError("queue body is not an S3, EventBridge, or replay event")


class PostgresIndex:
    """Transactional RDS index for immutable S3 batches."""

    def __init__(self, connection, campaign="ecc2k-130"):
        self.connection = connection
        self.campaign = campaign

    def assert_schema(self):
        required = {
            "distinguished_points": {
                "campaign_id",
                "point_key",
                "a",
                "b",
                "walk_seed",
                "worker_id",
                "found_at",
            },
            "ecc2k130_commits": {
                "campaign_id",
                "object_key",
                "manifest_key",
                "sha256",
                "bytes",
                "records",
                "slot",
                "stream_id",
                "byte_offset",
                "produced_at",
                "added",
                "collisions",
                "committed_at",
            },
            "ecc2k130_checkpoints": {
                "campaign_id",
                "slot",
                "object_key",
                "sha256",
                "iteration_base",
                "walks",
                "iterations",
                "produced_at",
                "updated_at",
            },
            "ecc2k130_checkpoint_objects": {
                "campaign_id",
                "object_key",
                "version_id",
                "slot",
                "iteration_base",
                "processed_at",
            },
            "dp_ingest_progress": {
                "campaign_id",
                "object_key",
                "records",
                "ingested_at",
            },
            "dp_ingest_totals": {
                "campaign_id",
                "dps",
                "first_dp_at",
                "last_dp_at",
            },
            "dp_ingest_hourly": {"campaign_id", "hour", "dps"},
            "rho_collisions": {"campaign_id", "point_key", "detected_at"},
            "rho_objects": {
                "campaign_id",
                "object_key",
                "slot",
                "stream_id",
                "byte_offset",
                "bytes",
                "records",
                "sha256",
                "fence",
                "uploaded_at",
            },
            "rho_slots": {
                "campaign_id",
                "slot",
                "owner",
                "lease_until",
                "fence",
                "state",
                "instance",
                "gpu",
                "gpu_name",
                "gpu_family",
                "instance_type",
                "iters",
                "points",
                "reason",
                "created_at",
                "claimed_at",
                "updated_at",
            },
        }
        required_types = {
            ("distinguished_points", "campaign_id"): "text",
            ("distinguished_points", "point_key"): "bytea",
            ("distinguished_points", "a"): "bytea",
            ("distinguished_points", "b"): "bytea",
            ("distinguished_points", "walk_seed"): "bytea",
            ("distinguished_points", "worker_id"): "text",
            ("distinguished_points", "found_at"): "timestamp with time zone",
            ("ecc2k130_commits", "campaign_id"): "text",
            ("ecc2k130_commits", "object_key"): "text",
            ("ecc2k130_commits", "manifest_key"): "text",
            ("ecc2k130_commits", "sha256"): "text",
            ("ecc2k130_commits", "bytes"): "bigint",
            ("ecc2k130_commits", "records"): "bigint",
            ("ecc2k130_commits", "slot"): "integer",
            ("ecc2k130_commits", "stream_id"): "text",
            ("ecc2k130_commits", "byte_offset"): "bigint",
            ("ecc2k130_commits", "produced_at"): "timestamp with time zone",
            ("ecc2k130_commits", "added"): "bigint",
            ("ecc2k130_commits", "collisions"): "bigint",
            ("ecc2k130_commits", "committed_at"): "timestamp with time zone",
            ("ecc2k130_checkpoints", "campaign_id"): "text",
            ("ecc2k130_checkpoints", "slot"): "integer",
            ("ecc2k130_checkpoints", "object_key"): "text",
            ("ecc2k130_checkpoints", "sha256"): "text",
            ("ecc2k130_checkpoints", "iteration_base"): "bigint",
            ("ecc2k130_checkpoints", "walks"): "bigint",
            ("ecc2k130_checkpoints", "iterations"): "numeric",
            ("ecc2k130_checkpoints", "produced_at"): "timestamp with time zone",
            ("ecc2k130_checkpoints", "updated_at"): "timestamp with time zone",
            ("ecc2k130_checkpoint_objects", "campaign_id"): "text",
            ("ecc2k130_checkpoint_objects", "object_key"): "text",
            ("ecc2k130_checkpoint_objects", "version_id"): "text",
            ("ecc2k130_checkpoint_objects", "slot"): "integer",
            ("ecc2k130_checkpoint_objects", "iteration_base"): "bigint",
            ("ecc2k130_checkpoint_objects", "processed_at"): "timestamp with time zone",
            ("dp_ingest_progress", "campaign_id"): "text",
            ("dp_ingest_progress", "object_key"): "text",
            ("dp_ingest_progress", "records"): "bigint",
            ("dp_ingest_progress", "ingested_at"): "timestamp with time zone",
            ("dp_ingest_totals", "campaign_id"): "text",
            ("dp_ingest_totals", "dps"): "bigint",
            ("dp_ingest_totals", "first_dp_at"): "timestamp with time zone",
            ("dp_ingest_totals", "last_dp_at"): "timestamp with time zone",
            ("dp_ingest_hourly", "campaign_id"): "text",
            ("dp_ingest_hourly", "hour"): "timestamp with time zone",
            ("dp_ingest_hourly", "dps"): "bigint",
            ("rho_collisions", "campaign_id"): "text",
            ("rho_collisions", "point_key"): "bytea",
            ("rho_collisions", "detected_at"): "timestamp with time zone",
            ("rho_objects", "campaign_id"): "text",
            ("rho_objects", "object_key"): "text",
            ("rho_objects", "slot"): "integer",
            ("rho_objects", "stream_id"): "text",
            ("rho_objects", "byte_offset"): "bigint",
            ("rho_objects", "bytes"): "bigint",
            ("rho_objects", "records"): "bigint",
            ("rho_objects", "sha256"): "text",
            ("rho_objects", "fence"): "bigint",
            ("rho_objects", "uploaded_at"): "bigint",
            ("rho_slots", "campaign_id"): "text",
            ("rho_slots", "slot"): "integer",
            ("rho_slots", "owner"): "text",
            ("rho_slots", "lease_until"): "bigint",
            ("rho_slots", "fence"): "bigint",
            ("rho_slots", "state"): "text",
            ("rho_slots", "instance"): "text",
            ("rho_slots", "gpu"): "integer",
            ("rho_slots", "gpu_name"): "text",
            ("rho_slots", "gpu_family"): "text",
            ("rho_slots", "instance_type"): "text",
            ("rho_slots", "iters"): "bigint",
            ("rho_slots", "points"): "bigint",
            ("rho_slots", "reason"): "text",
            ("rho_slots", "created_at"): "bigint",
            ("rho_slots", "claimed_at"): "bigint",
            ("rho_slots", "updated_at"): "bigint",
        }
        required_keys = {
            "distinguished_points": ("campaign_id", "point_key"),
            "ecc2k130_commits": ("campaign_id", "object_key"),
            "ecc2k130_checkpoints": ("campaign_id", "slot"),
            "ecc2k130_checkpoint_objects": (
                "campaign_id",
                "object_key",
                "version_id",
            ),
            "dp_ingest_progress": ("campaign_id", "object_key"),
            "dp_ingest_totals": ("campaign_id",),
            "dp_ingest_hourly": ("campaign_id", "hour"),
            "rho_collisions": ("campaign_id", "point_key"),
            "rho_objects": ("campaign_id", "object_key"),
            "rho_slots": ("campaign_id", "slot"),
        }
        tables = list(required)
        with self.connection.transaction(), self.connection.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = ANY(current_schemas(false))
                  AND table_name = ANY(%s)
                """,
                (tables,),
            )
            present = {table: {} for table in tables}
            for table, column, data_type in cur.fetchall():
                present[table][column] = data_type
            cur.execute(
                """
                SELECT tc.table_name,
                       array_agg(kcu.column_name::text ORDER BY kcu.ordinal_position)
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                 AND kcu.table_name = tc.table_name
                WHERE tc.table_schema = ANY(current_schemas(false))
                  AND tc.table_name = ANY(%s)
                  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                GROUP BY tc.table_name, tc.constraint_name
                """,
                (tables,),
            )
            keys = {table: [] for table in tables}
            for table, columns in cur.fetchall():
                keys[table].append(tuple(columns))
        missing = {
            table: sorted(columns - set(present[table]))
            for table, columns in required.items()
            if columns - set(present[table])
        }
        if missing:
            raise RuntimeError(f"ECC2K-130 schema is incomplete: {missing}")
        wrong_types = {
            f"{table}.{column}": {
                "expected": expected,
                "actual": present[table].get(column),
            }
            for (table, column), expected in required_types.items()
            if present[table].get(column) != expected
        }
        if wrong_types:
            raise RuntimeError(f"ECC2K-130 schema has incompatible types: {wrong_types}")
        missing_keys = {
            table: columns
            for table, columns in required_keys.items()
            if columns not in keys[table]
        }
        if missing_keys:
            raise RuntimeError(
                f"ECC2K-130 schema is missing unique keys: {missing_keys}"
            )
        return True

    def commit(self, batch):
        key = batch.object_key
        worker_id = "s3-" + key.key[len("dp/") :].replace("/", "-")
        found_at = batch.produced_at

        with self.connection.transaction():  # noqa: SIM117 - transaction must enter first
            with self.connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ecc2k130_commits
                      (campaign_id, object_key, manifest_key, sha256, bytes, records,
                       slot, stream_id, byte_offset, produced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (campaign_id, object_key) DO NOTHING
                    RETURNING object_key
                    """,
                    (
                        self.campaign,
                        key.key,
                        batch.manifest_key,
                        batch.sha256,
                        len(batch.body),
                        len(batch.records),
                        key.slot,
                        key.stream_id,
                        key.offset,
                        found_at,
                    ),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        """
                        SELECT sha256, records, committed_at
                        FROM ecc2k130_commits
                        WHERE campaign_id = %s AND object_key = %s
                        """,
                        (self.campaign, key.key),
                    )
                    previous = cur.fetchone()
                    if previous is None:
                        raise RuntimeError("object commit lost without a conflicting row")
                    if previous[0] != batch.sha256 or int(previous[1]) != len(batch.records):
                        raise RuntimeError("object key is already committed with different bytes")
                    return {
                        "status": "duplicate",
                        "objectKey": key.key,
                        "records": len(batch.records),
                        "added": 0,
                        "collisions": 0,
                    }

                cur.execute(
                    """
                    CREATE TEMP TABLE ecc2k130_dp_in
                      (point_key bytea, a bytea, b bytea, walk_seed bytea)
                    ON COMMIT DROP
                    """
                )
                with cur.copy(
                    "COPY ecc2k130_dp_in "
                    "(point_key, a, b, walk_seed) FROM STDIN (FORMAT BINARY)"
                ) as copy:
                    copy.set_types(["bytea", "bytea", "bytea", "bytea"])
                    for point in sorted(batch.records, key=lambda p: p.point_key):
                        copy.write_row(
                            (point.point_key, point.a, point.b, point.walk_seed)
                        )

                cur.execute(
                    """
                    INSERT INTO distinguished_points
                      (campaign_id, point_key, a, b, walk_seed, worker_id, found_at)
                    SELECT %s, point_key, a, b, walk_seed, %s, %s
                    FROM ecc2k130_dp_in
                    ORDER BY point_key
                    ON CONFLICT (campaign_id, point_key) DO NOTHING
                    """,
                    (self.campaign, worker_id, found_at),
                )
                added = cur.rowcount

                # The existing live collision table has changed shape over
                # time.  campaign_id + point_key is its stable contract; the
                # immutable object retains both seeds for independent replay.
                cur.execute(
                    """
                    INSERT INTO rho_collisions (campaign_id, point_key)
                    SELECT DISTINCT %s, i.point_key
                    FROM ecc2k130_dp_in i
                    JOIN distinguished_points d
                      ON d.campaign_id = %s AND d.point_key = i.point_key
                    WHERE d.a IS NOT NULL AND d.a IS DISTINCT FROM i.a
                    ON CONFLICT DO NOTHING
                    """,
                    (self.campaign, self.campaign),
                )
                collisions = cur.rowcount

                # Preserve the old dashboard tables during cutover.  They are
                # now written transactionally by events, not by an S3 poller.
                cur.execute(
                    """
                    INSERT INTO dp_ingest_progress
                      (campaign_id, object_key, records)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (campaign_id, object_key) DO UPDATE
                      SET records = EXCLUDED.records, ingested_at = now()
                    """,
                    (self.campaign, key.key, len(batch.records)),
                )
                if added:
                    cur.execute(
                        """
                        INSERT INTO dp_ingest_totals
                          (campaign_id, dps, first_dp_at, last_dp_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (campaign_id) DO UPDATE SET
                          dps = dp_ingest_totals.dps + EXCLUDED.dps,
                          first_dp_at = least(dp_ingest_totals.first_dp_at,
                                              EXCLUDED.first_dp_at),
                          last_dp_at = greatest(dp_ingest_totals.last_dp_at,
                                               EXCLUDED.last_dp_at)
                        """,
                        (self.campaign, added, found_at, found_at),
                    )
                    cur.execute(
                        """
                        INSERT INTO dp_ingest_hourly (campaign_id, hour, dps)
                        VALUES (%s, date_trunc('hour', %s::timestamptz), %s)
                        ON CONFLICT (campaign_id, hour) DO UPDATE SET
                          dps = dp_ingest_hourly.dps + EXCLUDED.dps
                        """,
                        (self.campaign, found_at, added),
                    )

                cur.execute(
                    """
                    INSERT INTO rho_objects
                      (campaign_id, object_key, slot, stream_id, byte_offset,
                       bytes, records, sha256, fence, uploaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                    ON CONFLICT (campaign_id, object_key) DO NOTHING
                    """,
                    (
                        self.campaign,
                        key.key,
                        key.slot,
                        key.stream_id,
                        key.offset,
                        len(batch.body),
                        len(batch.records),
                        batch.sha256,
                        int(found_at.timestamp()),
                    ),
                )
                cur.execute(
                    """
                    UPDATE ecc2k130_commits
                    SET added = %s, collisions = %s, committed_at = now()
                    WHERE campaign_id = %s AND object_key = %s
                    """,
                    (added, collisions, self.campaign, key.key),
                )

        return {
            "status": "committed",
            "objectKey": key.key,
            "records": len(batch.records),
            "added": added,
            "collisions": collisions,
        }

    def commit_checkpoint(self, checkpoint):
        """Keep the furthest cumulative checkpoint for each run id."""
        with self.connection.transaction(), self.connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ecc2k130_checkpoint_objects
                  (campaign_id, object_key, version_id, slot, iteration_base)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, object_key, version_id) DO NOTHING
                RETURNING object_key
                """,
                (
                    self.campaign,
                    checkpoint.object_key,
                    checkpoint.version_id,
                    checkpoint.slot,
                    checkpoint.iteration_base,
                ),
            )
            if cur.fetchone() is None:
                return {
                    "status": "duplicate-checkpoint",
                    "objectKey": checkpoint.object_key,
                    "slot": checkpoint.slot,
                    "iterations": checkpoint.iterations,
                }
            cur.execute(
                """
                INSERT INTO ecc2k130_checkpoints
                  (campaign_id, slot, object_key, sha256, iteration_base,
                   walks, iterations, produced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, slot) DO UPDATE SET
                  object_key = EXCLUDED.object_key,
                  sha256 = EXCLUDED.sha256,
                  iteration_base = EXCLUDED.iteration_base,
                  walks = EXCLUDED.walks,
                  iterations = EXCLUDED.iterations,
                  produced_at = EXCLUDED.produced_at,
                  updated_at = now()
                WHERE ecc2k130_checkpoints.iteration_base <= EXCLUDED.iteration_base
                RETURNING iteration_base
                """,
                (
                    self.campaign,
                    checkpoint.slot,
                    checkpoint.object_key,
                    checkpoint.sha256,
                    checkpoint.iteration_base,
                    checkpoint.walks,
                    checkpoint.iterations,
                    checkpoint.produced_at,
                ),
            )
            changed = cur.fetchone() is not None
        return {
            "status": "checkpoint" if changed else "older-checkpoint",
            "objectKey": checkpoint.object_key,
            "slot": checkpoint.slot,
            "iterations": checkpoint.iterations,
        }

    def status(self):
        """Return the fixed-cost public aggregates; no corpus table scan."""
        now = dt.datetime.now(tz=dt.timezone.utc)
        with self.connection.transaction(), self.connection.cursor() as cur:
            cur.execute(
                """
                    SELECT dps, first_dp_at, last_dp_at
                    FROM dp_ingest_totals WHERE campaign_id = %s
                    """,
                (self.campaign,),
            )
            total = cur.fetchone() or (0, None, None)
            cur.execute(
                """
                    SELECT hour, dps FROM dp_ingest_hourly
                    WHERE campaign_id = %s
                      AND hour >= date_trunc('hour', now() - interval '48 hours')
                    ORDER BY hour
                    """,
                (self.campaign,),
            )
            hourly = cur.fetchall()
            cur.execute(
                """
                    SELECT count(*), max(detected_at)
                    FROM rho_collisions WHERE campaign_id = %s
                    """,
                (self.campaign,),
            )
            collision_count, collision_at = cur.fetchone() or (0, None)
            cur.execute(
                """
                    SELECT count(*),
                           count(*) FILTER (
                             WHERE produced_at >= now() - interval '30 minutes'),
                           COALESCE(sum(iterations), 0)
                    FROM ecc2k130_checkpoints WHERE campaign_id = %s
                    """,
                (self.campaign,),
            )
            slots, walking, iterations = cur.fetchone() or (0, 0, 0)

        last_dp = total[2]
        recent_hour = sum(
            int(count)
            for hour, count in hourly
            if hour >= now - dt.timedelta(hours=1)
        )
        recent_day = sum(
            int(count)
            for hour, count in hourly
            if hour >= now - dt.timedelta(days=1)
        )
        return {
            "campaign_id": self.campaign,
            "curve_id": "certicom-ecc2k-130",
            "dp_mask_bits": 32,
            "campaign_created_at": "2026-09-11T17:51:35Z",
            "claim_boundary": (
                "Public research campaign aggregates for Certicom ECC2K-130 "
                "distinguished-point collection. A collision is not a recovered "
                "discrete logarithm until an independent solver verifies [k]P = Q."
            ),
            "collisions": int(collision_count),
            "latest_collision_at": _iso(collision_at),
            "dps": int(total[0]),
            "dps_last_hour": recent_hour,
            "dps_last_day": recent_day,
            "first_dp_at": _iso(total[1]),
            "last_dp_at": _iso(last_dp),
            "hourly": [
                {"hour": _iso(hour), "dps": int(count)} for hour, count in hourly
            ],
            "walkers": int(walking),
            "work": {
                "iterations": int(iterations),
                "iterations_log2": (
                    round(math.log2(int(iterations)), 6) if iterations else None
                ),
                "slots": int(slots),
                "walking_slots": int(walking),
                "density_independent": True,
                "method": "sum of latest S3 checkpoint iteration bases times walks",
            },
            "ingest": {
                "lag_seconds": (
                    max(0, int((now - last_dp).total_seconds())) if last_dp else None
                ),
                "newest_object_at": _iso(last_dp),
                "outstanding_objects": 0,
                "unrecognised_objects": 0,
            },
        }


def process_message(payload, config, s3, index):
    results = []
    for bucket, key, event_time, version_id in _event_jobs(payload):
        if key.endswith(".ck"):
            checkpoint = load_checkpoint(
                s3, config, bucket, key, event_time, version_id
            )
            results.append(index.commit_checkpoint(checkpoint))
        else:
            batch = load_batch(s3, config, bucket, key, event_time)
            results.append(index.commit(batch))
    return results


def _iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def publish_status(config, s3, index, queue_status=None):
    """Publish the dashboard feed from RDS without listing the S3 corpus."""
    status = index.status()
    now = dt.datetime.now(tz=dt.timezone.utc)
    queue_status = dict(queue_status or {})
    backlog = int(queue_status.get("messages") or 0)
    status["ingest"]["outstanding_objects"] = backlog
    status["queue"] = queue_status
    if status["collisions"]:
        state = "COLLISION_RECORDED"
    elif backlog or queue_status.get("state") in ("yellow", "red"):
        state = "INGEST_BEHIND"
    elif status["walkers"]:
        state = "COLLECTING"
    elif status["dps"]:
        state = "IDLE_OR_STALE"
    else:
        state = "EMPTY"
    status.update(
        schema_version=2,
        generated_at=_iso(now),
        published_at=_iso(now),
        source="cryptanalysis ECC2K-130 S3/Redis Streams/RDS integration",
        state=state,
    )
    body = (json.dumps(status, indent=2, sort_keys=True) + "\n").encode()
    s3.put_object(
        Bucket=config.status_bucket,
        Key="status.json",
        Body=body,
        ContentType="application/json",
        CacheControl="public, max-age=30",
    )
    return status


def database_url(config, secrets):
    if config.db_url:
        return config.db_url
    value = secrets.get_secret_value(SecretId=config.db_secret)["SecretString"]
    secret = json.loads(value)
    name = config.db_name or secret.get("dbname") or "postgres"
    port = int(secret.get("port") or 5432)
    user = urllib.parse.quote(secret["username"], safe="")
    password = urllib.parse.quote(secret["password"], safe="")
    database = urllib.parse.quote(name, safe="")
    sslmode = urllib.parse.quote(config.db_sslmode, safe="")
    return (
        f"postgresql://{user}:{password}@{config.db_host}:{port}/"
        f"{database}?sslmode={sslmode}"
    )


if __name__ == "__main__":
    raise SystemExit("run service.py for the Redis Streams consumer; see README.md")
