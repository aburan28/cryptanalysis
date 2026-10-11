import datetime as dt
import hashlib
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import handler
import publish_api


class FakeQueue:
    def __init__(self):
        self.calls = []

    def publish(self, bucket, key, **metadata):
        self.calls.append((bucket, key, metadata))
        return {"id": "1-0", "pressure": "green", "duplicate": False}


class FakeS3:
    def __init__(self, size, version_id="", versioning="Enabled"):
        self.size = size
        self.version_id = version_id
        self.versioning = versioning
        self.calls = []

    def head_object(self, **request):
        self.calls.append(request)
        return {
            "ContentLength": self.size,
            "VersionId": self.version_id,
            "LastModified": dt.datetime.now(tz=dt.timezone.utc),
        }

    def get_bucket_versioning(self, Bucket):
        return {"Status": self.versioning}


def config(campaign_id=""):
    return handler.Config(
        campaign="ecc2k-130",
        campaign_id=campaign_id,
        bucket="campaign",
        status_bucket="status",
        redis_url="rediss://memorydb.example",
        db_url="postgresql://example",
        db_host="",
        db_secret="",
        db_name="",
        db_sslmode="require",
    )


def dp_key():
    body = struct.pack("<QQQQ", 7, 11, 12, 3)
    digest = hashlib.sha256(body).hexdigest()
    return f"dp/slot-00140/{'b' * 32}-{0:016d}-{digest}.bin"


class PublisherTests(unittest.TestCase):
    def test_api_derives_size_and_records_from_s3(self):
        queue, s3 = FakeQueue(), FakeS3(32)
        result = publish_api.Publisher(config(), queue, s3).publish(
            {"bucket": "campaign", "key": dp_key()}
        )
        self.assertEqual(result["id"], "1-0")
        self.assertEqual(queue.calls[0][2]["size"], 32)
        self.assertEqual(queue.calls[0][2]["records"], 1)

    def test_wrong_bucket_cannot_poison_the_dedupe_identity(self):
        queue = FakeQueue()
        with self.assertRaisesRegex(ValueError, "ECC_BUCKET"):
            publish_api.Publisher(config(), queue, FakeS3(32)).publish(
                {"bucket": "other", "key": dp_key()}
            )
        self.assertEqual(queue.calls, [])

    def test_oversized_dp_is_refused_before_enqueue(self):
        queue = FakeQueue()
        with self.assertRaisesRegex(ValueError, "exceeds"):
            publish_api.Publisher(
                config(), queue, FakeS3(handler.MAX_DP_OBJECT_BYTES + 32)
            ).publish({"key": dp_key()})
        self.assertEqual(queue.calls, [])

    def test_strict_campaign_requires_the_sidecar_to_exist(self):
        s3 = FakeS3(32)
        publish_api.Publisher(config("a" * 64), FakeQueue(), s3).publish(
            {"key": dp_key()}
        )
        self.assertEqual(s3.calls[-1]["Key"], dp_key() + ".json")

    def test_mutable_checkpoint_uses_s3_version_identity(self):
        queue = FakeQueue()
        publish_api.Publisher(config(), queue, FakeS3(40, "version-7")).publish(
            {"key": "ckpt/slot-00140.ck"}
        )
        self.assertEqual(queue.calls[0][2]["version_id"], "version-7")

    def test_unversioned_mutable_checkpoint_is_refused(self):
        with self.assertRaisesRegex(ValueError, "versioning"):
            publish_api.Publisher(config(), FakeQueue(), FakeS3(40)).publish(
                {"key": "ckpt/slot-00140.ck"}
            )

    def test_suspended_bucket_and_null_version_are_refused(self):
        for s3 in (
            FakeS3(40, "version-1", versioning="Suspended"),
            FakeS3(40, "null"),
        ):
            with self.subTest(
                version=s3.version_id, status=s3.versioning
            ), self.assertRaisesRegex(ValueError, "versioning"):
                publish_api.Publisher(config(), FakeQueue(), s3).publish(
                    {"key": "ckpt/slot-00140.ck"}
                )


if __name__ == "__main__":
    unittest.main()
