"""Local gateway and contributor transport checks; no GPU or RDS required."""

from __future__ import annotations

from http.client import HTTPConnection
from pathlib import Path
from io import BytesIO
import json
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import API, ensure_identity, upload_checkpoint, upload_dps
from ingest import process_one
from protocol import HEADER
from server import Gateway, database
from seed_registry import S3Registry
from deploy.enable_ingest import dsn


class FakeStore:
    def __init__(self):
        self.rows = []

    def report_many(self, rows, **kwargs):
        self.rows.extend(rows)
        return [{"is_new": index == 0, "is_collision": index == 1,
                 "collision_id": 7 if index == 1 else None,
                 "prior_worker": "earlier" if index == 1 else None}
                for index, _ in enumerate(rows)]


class FakeRegistry:
    def __init__(self):
        self.reserved = set()

    def reserve(self, run_id):
        if run_id in self.reserved:
            return False
        self.reserved.add(run_id)
        return True


class FakeS3:
    def __init__(self):
        self.objects = {"seed-registry/curve-131/config.json": b'{"version":1,"state":"ready"}'}

    def get_object(self, *, Bucket, Key):
        return {"Body": BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        if Key in self.objects:
            class Conflict(Exception):
                response = {"ResponseMetadata": {"HTTPStatusCode": 412},
                            "Error": {"Code": "PreconditionFailed"}}
            raise Conflict()
        self.objects[Key] = Body


class PublicGatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = FakeRegistry()
        self.server = Gateway(("127.0.0.1", 0), self.root / "server", 50000, 50002,
                              "a-secret-for-invited-contributors", self.registry)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def raw(self, method, path, body=b"", headers=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = response.read()
        status = response.status
        conn.close()
        return status, result

    def test_auth_offsets_validation_and_restart(self):
        self.assertEqual(self.raw("POST", "/v1/register")[0], 401)
        api = API(self.url, "a-secret-for-invited-contributors")
        local = self.root / "worker"
        local.mkdir()
        state = ensure_identity(api, local)
        self.assertEqual(api.run_id, 50000)
        self.assertEqual((local / "state.json").stat().st_mode & 0o777, 0o600)
        record1 = struct.pack("<Q", 50000 << 48) + (3).to_bytes(24, "little")
        record2 = struct.pack("<Q", (50000 << 48) | 1) + (5).to_bytes(24, "little")
        (local / "dps.bin").write_bytes(record1 + record2)
        self.assertEqual(upload_dps(api, local, state), 64)
        self.assertEqual(state["remote_cursor"], 64)
        self.assertEqual(api.request("GET", "/v1/runs/50000")["cursor"], 64)
        # Retrying the same offset with the same bytes is idempotent.
        status, _ = self.raw("POST", "/v1/runs/50000/dps?offset=0", record1 + record2,
                             {"Authorization": "Bearer " + api.token})
        self.assertEqual(status, 200)
        status, _ = self.raw("POST", "/v1/runs/50000/dps?offset=0", record2,
                             {"Authorization": "Bearer " + api.token})
        self.assertEqual(status, 409)
        wrong_seed = struct.pack("<Q", 50001 << 48) + (3).to_bytes(24, "little")
        status, _ = self.raw("POST", "/v1/runs/50000/dps?offset=64", wrong_seed,
                             {"Authorization": "Bearer " + api.token})
        self.assertEqual(status, 400)
        field_words = 16 * 1088
        checkpoint = (HEADER.pack(b"ECC2K130", 0x100, 131, 256, 16, 1, 50000, 42)
                      + struct.pack("<iIQ", 32, field_words, 2**32) + b"\0" * 48
                      + b"\0" * (2 * field_words * 4 + 256 * 16 * 20))
        (local / "state.ck").write_bytes(checkpoint)
        upload_checkpoint(api, local, state)
        self.assertEqual(api.request("GET", "/v1/runs/50000/checkpoint"), checkpoint)
        self.assertEqual(ensure_identity(api, local)["remote_cursor"], 64)
        with self.assertRaises(ValueError):
            Gateway(("127.0.0.1", 0), self.root / "server", 51000, 51002,
                    "a-secret-for-invited-contributors", self.registry)
        self.assertEqual(self.registry.reserved, {50000})

    def test_ingest_retains_raw_and_collision_receipt(self):
        api = API(self.url, "a-secret-for-invited-contributors")
        local = self.root / "worker"
        local.mkdir()
        state = ensure_identity(api, local)
        records = b"".join(struct.pack("<Q", (50000 << 48) | i) +
                           (3 + 2 * i).to_bytes(24, "little") for i in range(2))
        (local / "dps.bin").write_bytes(records)
        upload_dps(api, local, state)
        fake = FakeStore()
        outcome = process_one(self.root / "server", fake)
        self.assertEqual(outcome["reported"], 2)
        self.assertEqual(outcome["collisions"], 1)
        self.assertEqual(len(fake.rows), 2)
        with database(self.root / "server/gateway.sqlite3") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM collision_records").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batches WHERE ingested_at IS NULL").fetchone()[0], 0)
        self.assertEqual(process_one(self.root / "server", fake), None)
        self.assertEqual(len(fake.rows), 2)

    def test_shared_seed_registry_reservation(self):
        s3 = FakeS3()
        registry = S3Registry("campaign-bucket", "public-v1", client=s3)
        registry.ready()
        self.assertTrue(registry.reserve(50000))
        self.assertFalse(registry.reserve(50000))
        self.assertIn(b'"active_owner": "public-gateway:public-v1:run50000"',
                      s3.objects["seed-registry/curve-131/run-50000.json"])

    def test_rds_dsn_encodes_secret_and_requires_verified_tls(self):
        connection = dsn({"username": "rho", "password": "@:#$", "dbname": "rho"},
                         "rho-dp.cxqyicswioh8.us-west-2.rds.amazonaws.com")
        self.assertIn("rho:%40%3A%23%24@rho-dp.", connection)
        self.assertIn("sslmode=verify-full", connection)
        self.assertIn("sslrootcert=%2Fopt%2Fecc2k130%2Frds-ca.pem", connection)

    def test_missing_walk_state_cannot_restart_or_reassign_seeds(self):
        api = API(self.url, "a-secret-for-invited-contributors")
        local = self.root / "worker"
        local.mkdir()
        (local / "dps.bin").write_bytes(b"")
        with self.assertRaisesRegex(RuntimeError, "without its run identity"):
            ensure_identity(api, local)
        self.assertEqual(self.registry.reserved, set())
        (local / "dps.bin").unlink()
        state = ensure_identity(api, local)
        record = struct.pack("<Q", 50000 << 48) + (3).to_bytes(24, "little")
        (local / "dps.bin").write_bytes(record)
        upload_dps(api, local, state)
        (local / "dps.bin").unlink()
        # A remote cursor can have advanced after upload but before the local
        # state file was saved; the gateway is authoritative in this case.
        state["remote_cursor"] = 0
        (local / "state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, "no checkpoint"):
            ensure_identity(api, local)
        self.assertFalse((local / "dps.bin").exists())


if __name__ == "__main__":
    unittest.main()
