import datetime as dt
import hashlib
import io
import os
import struct
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import handler
import reconcile
import service
import stream

DATABASE_URL = os.environ.get("ECC2K130_TEST_DATABASE_URL")
REDIS_URL = os.environ.get("ECC2K130_TEST_REDIS_URL")


class FakeS3:
    def __init__(self, key, body):
        self.key = key
        self.body = body

    def get_object(self, Bucket, Key, VersionId=None, Range=None):
        if Key == self.key:
            return {"Body": io.BytesIO(self.body)}
        raise KeyError(Key)

    def put_object(self, **_kwargs):
        return {}

    def head_object(self, **_kwargs):
        raise KeyError(_kwargs["Key"])

    def list_objects_v2(self, **_kwargs):
        if _kwargs.get("Prefix") == "dp/":
            return {
                "Contents": [
                    {
                        "Key": self.key,
                        "Size": len(self.body),
                        "LastModified": dt.datetime.now(tz=dt.timezone.utc),
                    }
                ],
                "IsTruncated": False,
            }
        return {"Contents": [], "IsTruncated": False}

    def list_object_versions(self, **_kwargs):
        return {"Versions": [], "IsTruncated": False}


@unittest.skipUnless(
    DATABASE_URL and REDIS_URL,
    "set ECC2K130_TEST_DATABASE_URL and ECC2K130_TEST_REDIS_URL",
)
class ServiceTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        import redis

        self.campaign = "test-" + uuid.uuid4().hex
        self.connection = psycopg.connect(DATABASE_URL, autocommit=False)
        with self.connection.cursor() as cur:
            cur.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
        self.connection.commit()

        queue_config = stream.QueueConfig(
            campaign=self.campaign,
            redis_url=REDIS_URL,
            consumer="integration",
            block_ms=10,
            batch_size=2,
            claim_idle_ms=10,
            max_deliveries=3,
            high_messages=10,
            critical_messages=20,
            high_bytes=1024,
            critical_bytes=2048,
            high_age_seconds=60,
            critical_age_seconds=120,
            high_memory_ratio=0.70,
            critical_memory_ratio=0.85,
        )
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.queue = stream.RedisStreamQueue(self.redis, queue_config)
        self.redis.delete(
            queue_config.stream,
            queue_config.stats,
            queue_config.pressure,
            queue_config.dead_letter,
            queue_config.queued,
            queue_config.pressure_sequence,
        )

    def tearDown(self):
        self.redis.delete(
            self.queue.config.stream,
            self.queue.config.stats,
            self.queue.config.pressure,
            self.queue.config.dead_letter,
            self.queue.config.queued,
            self.queue.config.pressure_sequence,
        )
        self.redis.close()
        with self.connection.cursor() as cur:
            for table in (
                "ecc2k130_checkpoint_objects",
                "rho_objects",
                "ecc2k130_commits",
                "dp_ingest_progress",
                "dp_ingest_hourly",
                "dp_ingest_totals",
                "rho_collisions",
                "distinguished_points",
            ):
                cur.execute(
                    f"DELETE FROM {table} WHERE campaign_id = %s", (self.campaign,)
                )
        self.connection.commit()
        self.connection.close()

    def test_s3_reference_flows_through_stream_and_rds_before_ack(self):
        body = struct.pack("<QQQQ", 7, 11, 12, 3)
        digest = hashlib.sha256(body).hexdigest()
        key = f"dp/slot-00140/{'b' * 32}-{0:016d}-{digest}.bin"
        config = handler.Config(
            campaign=self.campaign,
            campaign_id="",
            bucket="bucket",
            status_bucket="status",
            redis_url=REDIS_URL,
            db_url=DATABASE_URL,
            db_host="",
            db_secret="",
            db_name="",
            db_sslmode="disable",
        )
        app = service.IndexService(
            config,
            self.queue,
            FakeS3(key, body),
            handler.PostgresIndex(self.connection, self.campaign),
            status_every=3600,
        )
        app.last_status = time.monotonic()
        self.queue.publish(
            "bucket",
            key,
            size=len(body),
            records=1,
            event_time=dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        )
        result = app.run_once()
        self.assertEqual(result["messages"][0]["status"], "acked")
        self.assertEqual(self.redis.xlen(self.queue.config.stream), 0)
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM distinguished_points WHERE campaign_id = %s",
                (self.campaign,),
            )
            self.assertEqual(cur.fetchone()[0], 1)
        self.connection.commit()

    def test_reconciler_repairs_upload_before_xadd_gap_without_duplicates(self):
        body = struct.pack("<QQQQ", 7, 11, 12, 3)
        digest = hashlib.sha256(body).hexdigest()
        key = f"dp/slot-00140/{'b' * 32}-{0:016d}-{digest}.bin"
        config = handler.Config(
            campaign=self.campaign,
            campaign_id="",
            bucket="bucket",
            status_bucket="status",
            redis_url=REDIS_URL,
            db_url=DATABASE_URL,
            db_host="",
            db_secret="",
            db_name="",
            db_sslmode="disable",
        )
        s3 = FakeS3(key, body)
        first = reconcile.reconcile(s3, self.queue, self.connection, config)
        second = reconcile.reconcile(s3, self.queue, self.connection, config)
        self.assertEqual(first["queued"], 1)
        self.assertEqual(second["alreadyQueued"], 1)

        app = service.IndexService(
            config,
            self.queue,
            s3,
            handler.PostgresIndex(self.connection, self.campaign),
            status_every=3600,
        )
        app.last_status = time.monotonic()
        app.run_once()
        after_commit = reconcile.reconcile(
            s3, self.queue, self.connection, config
        )
        self.assertEqual(after_commit["queued"], 0)
        self.assertEqual(self.redis.xlen(self.queue.config.stream), 0)

    def test_strict_reconciler_waits_for_commit_marker(self):
        body = struct.pack("<QQQQ", 7, 11, 12, 3)
        digest = hashlib.sha256(body).hexdigest()
        key = f"dp/slot-00140/{'b' * 32}-{0:016d}-{digest}.bin"
        config = handler.Config(
            campaign=self.campaign,
            campaign_id="a" * 64,
            bucket="bucket",
            status_bucket="status",
            redis_url=REDIS_URL,
            db_url=DATABASE_URL,
            db_host="",
            db_secret="",
            db_name="",
            db_sslmode="disable",
        )
        result = reconcile.reconcile(
            FakeS3(key, body), self.queue, self.connection, config
        )
        self.assertEqual(result["uncommitted"], 1)
        self.assertEqual(result["queued"], 0)
        self.assertEqual(self.redis.xlen(self.queue.config.stream), 0)


if __name__ == "__main__":
    unittest.main()
