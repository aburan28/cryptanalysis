import hashlib
import io
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import handler


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.puts = []

    def get_object(self, Bucket, Key, VersionId=None, Range=None):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)


class FakeIndex:
    def __init__(self):
        self.batches = []

    def commit(self, batch):
        self.batches.append(batch)
        return {
            "status": "committed",
            "objectKey": batch.object_key.key,
            "records": len(batch.records),
            "added": len(batch.records),
            "collisions": 0,
        }

    def commit_checkpoint(self, checkpoint):
        self.batches.append(checkpoint)
        return {
            "status": "checkpoint",
            "objectKey": checkpoint.object_key,
            "slot": checkpoint.slot,
            "iterations": checkpoint.iterations,
        }

    def status(self):
        return {
            "campaign_id": "ecc2k-130",
            "collisions": 0,
            "dps": 2,
            "walkers": 1,
            "ingest": {"outstanding_objects": 0},
        }


def config(campaign_id=""):
    return handler.Config(
        campaign="ecc2k-130",
        campaign_id=campaign_id,
        bucket="ecc2k130-test",
        status_bucket="ecc2k130-status-test",
        redis_url="rediss://memorydb.example:6379",
        db_url="postgresql://example/db",
        db_host="",
        db_secret="rho/dp-rds",
        db_name="",
        db_sslmode="require",
    )


def fixture(campaign_id="a" * 64):
    body = struct.pack("<QQQQ", 7, 11, 12, 3) + struct.pack(
        "<QQQQ", 8, 21, 22, 1
    )
    digest = hashlib.sha256(body).hexdigest()
    key = f"dp/slot-00140/{'b' * 32}-{791392:016d}-{digest}.bin"
    manifest = {
        "protocol": handler.PROTOCOL,
        "campaignId": campaign_id,
        "kind": "dp",
        "bytes": len(body),
        "records": 2,
        "sha256": digest,
        "producedAt": 1789311001,
    }
    return body, key, manifest


def checkpoint_fixture():
    slot = 140
    body = handler.CHECKPOINT_HEADER.pack(
        b"ECC2K130", 2, 131, 128, 16, 1, slot + 1, 1000
    )
    digest = hashlib.sha256(body).hexdigest()
    return body, f"ckpt/slot-{slot:05d}/{digest}.ck"


class ProtocolTests(unittest.TestCase):
    def test_parses_the_live_content_addressed_key(self):
        _, key, _ = fixture()
        parsed = handler.parse_object_key(key)
        self.assertEqual(parsed.slot, 140)
        self.assertEqual(parsed.offset, 791392)
        self.assertEqual(len(parsed.sha256), 64)

    def test_rejects_legacy_uncommitted_keys(self):
        with self.assertRaisesRegex(ValueError, "strict DP object"):
            handler.parse_object_key(
                "dp/slot-00002/1789311001-0000000000000000.bin"
            )

    def test_rejects_slot_outside_run_id_space(self):
        key = "dp/slot-65535/" + "a" * 32 + "-" + "0" * 16 + "-" + "b" * 64 + ".bin"
        with self.assertRaisesRegex(ValueError, "run-id"):
            handler.parse_object_key(key)

    def test_decodes_the_packed_record_contract(self):
        body, _, _ = fixture()
        rows = handler.decode_records(body)
        self.assertEqual(len(rows), 2)
        self.assertEqual(int.from_bytes(rows[0].a, "big"), 7)
        self.assertEqual(rows[0].point_key, body[8:32])
        self.assertEqual(rows[0].b, bytes(17))

    def test_refuses_a_partial_or_empty_record(self):
        for body in (b"", bytes(31), bytes(33)):
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                handler.decode_records(body)

    def test_decodes_checkpoint_work_from_the_header(self):
        body, key = checkpoint_fixture()
        checkpoint = handler.load_checkpoint(
            FakeS3({key: body}), config(""), "ecc2k130-test", key
        )
        self.assertEqual(checkpoint.slot, 140)
        self.assertEqual(checkpoint.walks, 128 * 16)
        self.assertEqual(checkpoint.iterations, 1000 * 128 * 16)

    def test_hashed_checkpoint_stream_is_verified(self):
        body, key = checkpoint_fixture()
        corrupted = body[:-1] + bytes([body[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "key hash"):
            handler.load_checkpoint(
                FakeS3({key: corrupted}), config(""), "ecc2k130-test", key
            )

    def test_mutable_checkpoint_is_bound_to_an_s3_version(self):
        body, _ = checkpoint_fixture()
        key = "ckpt/slot-00140.ck"
        with self.assertRaisesRegex(ValueError, "VersionId"):
            handler.load_checkpoint(
                FakeS3({key: body}), config(""), "ecc2k130-test", key
            )
        checkpoint = handler.load_checkpoint(
            FakeS3({key: body}),
            config(""),
            "ecc2k130-test",
            key,
            version_id="version-7",
        )
        self.assertEqual(checkpoint.version_id, "version-7")


class BatchTests(unittest.TestCase):
    def test_strict_payload_and_manifest_are_verified(self):
        body, key, manifest = fixture()
        s3 = FakeS3(
            {key: body, key + ".json": json.dumps(manifest).encode("utf-8")}
        )
        batch = handler.load_batch(
            s3, config(manifest["campaignId"]), "ecc2k130-test", key
        )
        self.assertEqual(batch.object_key.key, key)
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(int(batch.produced_at.timestamp()), 1789311001)

    def test_live_legacy_campaign_accepts_a_hashed_payload_without_sidecar(self):
        body, key, _ = fixture()
        batch = handler.load_batch(
            FakeS3({key: body}), config(""), "ecc2k130-test", key
        )
        self.assertEqual(batch.sha256, hashlib.sha256(body).hexdigest())

    def test_strict_campaign_requires_the_sidecar(self):
        body, key, manifest = fixture()
        with self.assertRaisesRegex(ValueError, "missing.*commit marker"):
            handler.load_batch(
                FakeS3({key: body}),
                config(manifest["campaignId"]),
                "ecc2k130-test",
                key,
            )

    def test_corruption_is_rejected_by_the_key_hash(self):
        body, key, _ = fixture()
        with self.assertRaisesRegex(ValueError, "key hash"):
            handler.load_batch(
                FakeS3({key: body[:-1] + b"x"}),
                config(""),
                "ecc2k130-test",
                key,
            )

    def test_wrong_campaign_is_rejected(self):
        body, key, manifest = fixture()
        s3 = FakeS3(
            {key: body, key + ".json": json.dumps(manifest).encode("utf-8")}
        )
        with self.assertRaisesRegex(ValueError, "another campaign"):
            handler.load_batch(s3, config("c" * 64), "ecc2k130-test", key)


class EventTests(unittest.TestCase):
    def test_native_s3_message_routes_only_payloads(self):
        _, key, _ = fixture()
        event = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "eventTime": "2026-09-20T13:00:00Z",
                    "s3": {
                        "bucket": {"name": "ecc2k130-test"},
                        "object": {"key": key.replace("/", "%2F")},
                    },
                },
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "ecc2k130-test"},
                        "object": {"key": "slots%2Fslot-00140.json"},
                    },
                },
            ]
        }
        self.assertEqual(
            list(handler._event_jobs(event)),
            [("ecc2k130-test", key, "2026-09-20T13:00:00Z", "")],
        )

    def test_checkpoint_message_updates_the_work_index(self):
        body, key = checkpoint_fixture()
        index = FakeIndex()
        results = handler.process_message(
            {"bucket": "ecc2k130-test", "manifestKey": key},
            config(""),
            FakeS3({key: body}),
            index,
        )
        self.assertEqual(results[0]["status"], "checkpoint")
        self.assertEqual(results[0]["iterations"], 1000 * 128 * 16)

    def test_s3_test_event_is_an_acknowledged_noop(self):
        self.assertEqual(list(handler._event_jobs({"Event": "s3:TestEvent"})), [])

    def test_message_is_committed_once(self):
        body, key, _ = fixture()
        index = FakeIndex()
        results = handler.process_message(
            {"bucket": "ecc2k130-test", "manifestKey": key},
            config(""),
            FakeS3({key: body}),
            index,
        )
        self.assertEqual(results[0]["records"], 2)
        self.assertEqual(len(index.batches), 1)

    def test_status_includes_redis_queue_pressure(self):
        s3 = FakeS3()
        queue = {
            "messages": 3,
            "pending": 1,
            "bytes": 64,
            "records": 2,
            "state": "yellow",
        }
        status = handler.publish_status(config(""), s3, FakeIndex(), queue)
        self.assertEqual(status["ingest"]["outstanding_objects"], 3)
        self.assertEqual(status["state"], "INGEST_BEHIND")
        self.assertEqual(status["queue"]["state"], "yellow")
        self.assertEqual(s3.puts[0]["Key"], "status.json")


if __name__ == "__main__":
    unittest.main()
