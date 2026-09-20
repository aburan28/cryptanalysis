import datetime as dt
import hashlib
import os
import struct
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import handler

DATABASE_URL = os.environ.get("ECC2K130_TEST_DATABASE_URL")


def batch(slot, stream, offset, records):
    body = b"".join(struct.pack("<Q", seed) + point for seed, point in records)
    digest = hashlib.sha256(body).hexdigest()
    key = f"dp/slot-{slot:05d}/{stream}-{offset:016d}-{digest}.bin"
    return handler.Batch(
        bucket="test",
        object_key=handler.parse_object_key(key),
        manifest_key=key + ".json",
        sha256=digest,
        body=body,
        records=handler.decode_records(body),
        produced_at=dt.datetime.now(tz=dt.timezone.utc),
    )


@unittest.skipUnless(DATABASE_URL, "set ECC2K130_TEST_DATABASE_URL for Postgres tests")
class PostgresIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.connection = psycopg.connect(DATABASE_URL, autocommit=False)
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        with cls.connection.cursor() as cur:
            cur.execute(schema)
        cls.connection.commit()

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def setUp(self):
        self.campaign = "test-" + uuid.uuid4().hex
        self.index = handler.PostgresIndex(self.connection, self.campaign)

    def tearDown(self):
        tables = (
            "ecc2k130_checkpoints",
            "rho_objects",
            "ecc2k130_commits",
            "dp_ingest_progress",
            "dp_ingest_hourly",
            "dp_ingest_totals",
            "rho_collisions",
            "distinguished_points",
        )
        with self.connection.cursor() as cur:
            for table in tables:
                cur.execute(f"DELETE FROM {table} WHERE campaign_id = %s", (self.campaign,))
        self.connection.commit()

    def test_object_commit_is_atomic_idempotent_and_detects_a_collision(self):
        point = struct.pack("<QQQ", 11, 12, 3)
        first = batch(140, "a" * 32, 0, [(7, point)])
        result = self.index.commit(first)
        self.assertEqual((result["added"], result["collisions"]), (1, 0))

        duplicate = self.index.commit(first)
        self.assertEqual(duplicate["status"], "duplicate")

        second = batch(141, "b" * 32, 32, [(8, point)])
        collision = self.index.commit(second)
        self.assertEqual((collision["added"], collision["collisions"]), (0, 1))

        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT dps FROM dp_ingest_totals WHERE campaign_id = %s",
                (self.campaign,),
            )
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute(
                "SELECT count(*) FROM rho_collisions WHERE campaign_id = %s",
                (self.campaign,),
            )
            self.assertEqual(cur.fetchone()[0], 1)
        self.connection.commit()

    def test_checkpoint_index_keeps_the_furthest_work(self):
        now = dt.datetime.now(tz=dt.timezone.utc)
        newer = handler.Checkpoint(
            bucket="test",
            object_key="ckpt/slot-00140/new.ck",
            slot=140,
            sha256="a" * 64,
            iteration_base=100,
            walks=2048,
            iterations=204800,
            produced_at=now,
        )
        older = handler.Checkpoint(
            bucket="test",
            object_key="ckpt/slot-00140/old.ck",
            slot=140,
            sha256="b" * 64,
            iteration_base=90,
            walks=2048,
            iterations=184320,
            produced_at=now,
        )
        self.assertEqual(self.index.commit_checkpoint(newer)["status"], "checkpoint")
        self.assertEqual(
            self.index.commit_checkpoint(older)["status"], "older-checkpoint"
        )
        status = self.index.status()
        self.assertEqual(status["work"]["iterations"], 204800)
        self.assertEqual(status["work"]["walking_slots"], 1)


if __name__ == "__main__":
    unittest.main()
