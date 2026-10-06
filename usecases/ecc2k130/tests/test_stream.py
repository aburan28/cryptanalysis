import hashlib
import os
import struct
import sys
import time
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import stream

REDIS_URL = os.environ.get("ECC2K130_TEST_REDIS_URL")


def dp_fixture():
    body = struct.pack("<QQQQ", 7, 11, 12, 3)
    digest = hashlib.sha256(body).hexdigest()
    key = f"dp/slot-00140/{'b' * 32}-{0:016d}-{digest}.bin"
    return body, key


def config(**overrides):
    values = {
        "campaign": "test-" + uuid.uuid4().hex,
        "redis_url": REDIS_URL or "redis://localhost:6379",
        "consumer": "test-consumer",
        "block_ms": 10,
        "batch_size": 8,
        "claim_idle_ms": 10,
        "max_deliveries": 3,
        "high_messages": 10,
        "critical_messages": 20,
        "high_bytes": 1024,
        "critical_bytes": 2048,
        "high_age_seconds": 60,
        "critical_age_seconds": 120,
        "high_memory_ratio": 0.70,
        "critical_memory_ratio": 0.85,
    }
    values.update(overrides)
    return stream.QueueConfig(**values)


class PressureTests(unittest.TestCase):
    def test_pressure_uses_lag_bytes_age_and_memory(self):
        cfg = config()
        base = {
            "messages": 0,
            "bytes": 0,
            "oldestAgeSeconds": 0,
            "memoryRatio": 0.0,
        }
        self.assertEqual(stream.pressure_state(base, cfg), "green")
        self.assertEqual(
            stream.pressure_state(dict(base, messages=cfg.high_messages), cfg),
            "yellow",
        )
        self.assertEqual(
            stream.pressure_state(dict(base, bytes=cfg.critical_bytes), cfg), "red"
        )
        self.assertEqual(
            stream.pressure_state(
                dict(base, memoryRatio=cfg.critical_memory_ratio), cfg
            ),
            "red",
        )

    def test_thresholds_must_leave_warning_headroom(self):
        with self.assertRaisesRegex(ValueError, "high < critical"):
            config(high_messages=10, critical_messages=10).validate()

    def test_cluster_memory_is_aggregated_and_noeviction_is_required(self):
        class Cluster:
            def __init__(self, policy):
                self.policy = policy

            def register_script(self, _script):
                return lambda **_kwargs: None

            def get_primaries(self):
                return ["node-a", "node-b"]

            def info(self, _section, target_nodes=None):
                if target_nodes != ["node-a", "node-b"]:
                    raise AssertionError("every primary must be queried")
                return {
                    "node-a": {
                        "used_memory": 10,
                        "maxmemory": 100,
                        "maxmemory_policy": self.policy,
                    },
                    "node-b": {
                        "used_memory": 20,
                        "maxmemory": 200,
                        "maxmemory_policy": self.policy,
                    },
                }

        cfg = config(backend="memorydb", cluster=True)
        queue = stream.RedisStreamQueue(Cluster("noeviction"), cfg)
        self.assertEqual(queue._memory_info()["maxmemory"], 300)
        self.assertEqual(queue._memory_info()["max_memory_ratio"], 0.1)
        self.assertTrue(queue.validate_server())
        with self.assertRaisesRegex(RuntimeError, "noeviction"):
            stream.RedisStreamQueue(Cluster("allkeys-lru"), cfg).validate_server()


@unittest.skipUnless(REDIS_URL, "set ECC2K130_TEST_REDIS_URL for Redis tests")
class RedisStreamTests(unittest.TestCase):
    def setUp(self):
        import redis

        self.client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.config = config()
        self.queue = stream.RedisStreamQueue(self.client, self.config)
        self.keys = (
            self.config.stream,
            self.config.stats,
            self.config.pressure,
            self.config.dead_letter,
            self.config.queued,
            self.config.pressure_sequence,
        )
        self.client.delete(*self.keys)

    def tearDown(self):
        self.client.delete(*self.keys)
        self.client.close()

    def test_success_is_acked_deleted_and_removed_from_pressure(self):
        body, key = dp_fixture()
        self.queue.publish("bucket", key, size=len(body), records=1)
        consumer = stream.StreamConsumer(self.queue)
        result = consumer.consume_once(lambda fields: fields["key"])
        self.assertEqual(result["messages"][0]["status"], "acked")
        self.assertEqual(self.client.xlen(self.config.stream), 0)
        pressure = self.queue.refresh_pressure()
        self.assertEqual((pressure["messages"], pressure["bytes"]), (0, 0))

    def test_hard_limit_rejects_before_redis_memory_is_exhausted(self):
        cfg = config(
            campaign=self.config.campaign,
            high_messages=1,
            critical_messages=2,
            high_bytes=1000,
            critical_bytes=2000,
        )
        queue = stream.RedisStreamQueue(self.client, cfg)
        body, original = dp_fixture()
        suffix = original.rsplit("-", 1)[1]
        keys = [
            f"dp/slot-00140/{offset:032x}-{offset:016d}-{suffix}"
            for offset in range(3)
        ]
        queue.publish("bucket", keys[0], size=len(body), records=1)
        queue.publish("bucket", keys[1], size=len(body), records=1)
        with self.assertRaises(stream.Backpressure) as caught:
            queue.publish("bucket", keys[2], size=len(body), records=1)
        self.assertEqual(caught.exception.messages, 2)
        self.assertEqual(self.client.xlen(cfg.stream), 2)

    def test_metadata_cannot_hide_dp_bytes_from_backpressure(self):
        _, key = dp_fixture()
        for size, records in ((0, 0), (-32, -1), (64, 1), (32, 0)):
            with self.subTest(size=size, records=records), self.assertRaises(
                ValueError
            ):
                self.queue.publish("bucket", key, size=size, records=records)
        too_large = self.config.max_dp_bytes + 32
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.queue.publish(
                "bucket", key, size=too_large, records=too_large // 32
            )
        self.assertEqual(self.client.xlen(self.config.stream), 0)

    def test_retried_object_reference_is_deduplicated(self):
        body, key = dp_fixture()
        first = self.queue.publish("bucket", key, size=len(body), records=1)
        second = self.queue.publish("bucket", key, size=len(body), records=1)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.client.xlen(self.config.stream), 1)

    def test_mutable_checkpoint_versions_have_distinct_queue_identity(self):
        key = "ckpt/slot-00140.ck"
        first = self.queue.publish(
            "bucket", key, size=40, records=0, version_id="version-1"
        )
        second = self.queue.publish(
            "bucket", key, size=40, records=0, version_id="version-2"
        )
        self.assertFalse(first["duplicate"])
        self.assertFalse(second["duplicate"])
        self.assertEqual(self.client.xlen(self.config.stream), 2)

    def test_older_pressure_snapshot_cannot_overwrite_a_newer_red_state(self):
        server_seconds = int(self.client.time()[0])
        self.client.hset(
            self.config.pressure,
            mapping={
                "version": (server_seconds + 60) * 1_000_000,
                "updatedAt": server_seconds + 60,
                "state": "red",
            },
        )
        self.queue.refresh_pressure()
        self.assertEqual(self.client.hget(self.config.pressure, "state"), "red")

    def test_permanent_poison_message_moves_to_dead_letter(self):
        cfg = config(campaign=self.config.campaign, max_deliveries=1)
        queue = stream.RedisStreamQueue(self.client, cfg)
        body, key = dp_fixture()
        queue.publish("bucket", key, size=len(body), records=1)
        result = stream.StreamConsumer(queue).consume_once(
            lambda _fields: (_ for _ in ()).throw(
                stream.PermanentMessageError("bad record")
            )
        )
        self.assertEqual(result["messages"][0]["status"], "dead-letter")
        self.assertEqual(self.client.xlen(cfg.stream), 0)
        self.assertEqual(self.client.xlen(cfg.dead_letter), 1)
        replay = queue.publish("bucket", key, size=len(body), records=1)
        self.assertTrue(replay["duplicate"])
        self.assertTrue(replay["id"].startswith("dead:"))
        self.assertEqual(self.client.xlen(cfg.stream), 0)

    def test_stale_consumer_cannot_dead_letter_the_new_owners_entry(self):
        body, key = dp_fixture()
        self.queue.publish("bucket", key, size=len(body), records=1)
        self.queue.ensure_group()
        message_id, fields = self.queue.read_new()[0]
        time.sleep(0.01)
        replacement = stream.RedisStreamQueue(
            self.client,
            replace(self.config, consumer="replacement", claim_idle_ms=1),
        )
        self.assertEqual(replacement.claim_stale()[0][0], message_id)
        stale = self.queue.dead_letter(message_id, fields, "stale")
        self.assertFalse(stale["acked"])
        self.assertEqual(self.client.xlen(self.config.dead_letter), 0)
        self.assertEqual(self.client.xlen(self.config.stream), 1)

    def test_infrastructure_failure_stays_pending_despite_delivery_limit(self):
        cfg = config(campaign=self.config.campaign, max_deliveries=1)
        queue = stream.RedisStreamQueue(self.client, cfg)
        body, key = dp_fixture()
        queue.publish("bucket", key, size=len(body), records=1)
        result = stream.StreamConsumer(queue).consume_once(
            lambda _fields: (_ for _ in ()).throw(ConnectionError("RDS down"))
        )
        self.assertEqual(result["messages"][0]["status"], "retry")
        self.assertEqual(self.client.xlen(cfg.stream), 1)
        self.assertEqual(self.client.xlen(cfg.dead_letter), 0)

    def test_replacement_consumer_reclaims_an_abandoned_pending_entry(self):
        body, key = dp_fixture()
        self.queue.publish("bucket", key, size=len(body), records=1)
        self.queue.ensure_group()
        abandoned = self.queue.read_new()
        self.assertEqual(len(abandoned), 1)
        time.sleep(0.01)

        replacement = stream.RedisStreamQueue(
            self.client,
            replace(self.config, consumer="replacement", claim_idle_ms=1),
        )
        claimed = replacement.claim_stale()
        self.assertEqual(claimed[0][0], abandoned[0][0])
        replacement.ack(claimed[0][0], claimed[0][1])
        self.assertEqual(self.client.xlen(self.config.stream), 0)

    def test_reclaim_cursor_advances_across_a_large_pending_list(self):
        body, original = dp_fixture()
        suffix = original.rsplit("-", 1)[1]
        for offset in range(6):
            key = (
                f"dp/slot-00140/{offset:032x}-{offset:016d}-{suffix}"
            )
            self.queue.publish("bucket", key, size=len(body), records=1)
        self.queue.ensure_group()
        self.assertEqual(len(self.queue.read_new()), 6)
        time.sleep(0.01)

        replacement = stream.RedisStreamQueue(
            self.client,
            replace(
                self.config,
                consumer="replacement",
                claim_idle_ms=1,
                batch_size=2,
            ),
        )
        claimed = []
        for _ in range(3):
            claimed.extend(replacement.claim_stale())
        self.assertEqual(len({message_id for message_id, _ in claimed}), 6)


if __name__ == "__main__":
    unittest.main()
