#!/usr/bin/env python3
"""Credential-free contributor gateway; TLS is supplied by the reverse proxy.

The gateway keeps raw uploads durable and separate from RDS.  ingest.py is the
only process allowed to write the existing collision pool.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

from protocol import (CAMPAIGN, DP_WEIGHT, WALK_ID, MAX_BATCH_BYTES,
                      MAX_CHECKPOINT_BYTES, check_checkpoint, check_records)
from seed_registry import S3Registry

RUN_PATH = re.compile(r"^/v1/runs/([1-9][0-9]*)(?:/(dps|checkpoint))?$")


@contextmanager
def database(path: Path):
    db = sqlite3.connect(path, timeout=30)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        with db:
            yield db
    finally:
        db.close()


def initialize(path: Path, start: int, end: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with database(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY, token_sha256 TEXT NOT NULL,
                created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                cursor INTEGER NOT NULL DEFAULT 0,
                checkpoint_path TEXT, checkpoint_at INTEGER);
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
                offset INTEGER NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                path TEXT NOT NULL, created_at INTEGER NOT NULL,
                ingested_at INTEGER, reported INTEGER, new_points INTEGER,
                collisions INTEGER,
                UNIQUE(run_id, offset));
            CREATE TABLE IF NOT EXISTS collision_records (
                batch_id INTEGER NOT NULL REFERENCES batches(id), index_in_batch INTEGER NOT NULL,
                seed TEXT NOT NULL, point_key_hex TEXT NOT NULL,
                collision_id INTEGER, prior_worker TEXT,
                PRIMARY KEY(batch_id, index_in_batch));
        """)
        expected = {"run_id_start": str(start), "run_id_end": str(end),
                    "campaign": CAMPAIGN, "walk_id": WALK_ID, "dp_weight": str(DP_WEIGHT)}
        for key, value in expected.items():
            row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            if row and row[0] != value:
                raise ValueError(f"state {key}={row[0]!r} disagrees with configured {value!r}")
            db.execute("INSERT OR IGNORE INTO config(key,value) VALUES (?,?)", (key, value))


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Gateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: Path, start: int, end: int, join_token: str,
                 registry):
        self.state = state
        self.db_path = state / "gateway.sqlite3"
        self.start_id, self.end_id = start, end
        self.join_hash = hashlib.sha256(join_token.encode()).digest()
        self.registry = registry
        initialize(self.db_path, start, end)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: Gateway
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Never log bearer or join tokens, query strings, or request bodies.
        print("%s %s" % (self.address_string(), fmt % args), flush=True)

    def respond(self, status: int, obj: dict) -> None:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def fail(self, status: int, reason: str) -> None:
        self.respond(status, {"error": reason})

    def body(self, limit: int) -> bytes:
        length = self.headers.get("Content-Length")
        if length is None or not length.isdecimal() or int(length) > limit:
            raise ValueError("missing or excessive Content-Length")
        data = self.rfile.read(int(length))
        if len(data) != int(length):
            raise ValueError("truncated request body")
        return data

    def authorized_run(self, db: sqlite3.Connection, run_id: int):
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        bearer = self.headers.get("Authorization", "")
        token = bearer[7:] if bearer.startswith("Bearer ") else ""
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not row or not token or not hmac.compare_digest(digest, row["token_sha256"]):
            return None
        return row

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            with database(self.server.db_path) as db:
                assigned = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                pending = db.execute("SELECT COUNT(*) FROM batches WHERE ingested_at IS NULL").fetchone()[0]
            return self.respond(200, {"ok": True, "campaign": CAMPAIGN,
                                      "assigned_runs": assigned, "pending_batches": pending})
        if path == "/v1/config":
            return self.respond(200, {"campaign": CAMPAIGN, "walk_id": WALK_ID,
                                      "dp_weight": DP_WEIGHT, "record_bytes": 32})
        match = RUN_PATH.fullmatch(path)
        if not match:
            return self.fail(404, "unknown endpoint")
        run_id, suffix = int(match[1]), match[2]
        with database(self.server.db_path) as db:
            row = self.authorized_run(db, run_id)
            if row is None:
                return self.fail(401, "invalid run token")
            if suffix is None:
                return self.respond(200, {"run_id": run_id, "cursor": row["cursor"],
                                          "checkpoint_at": row["checkpoint_at"]})
            if suffix != "checkpoint" or not row["checkpoint_path"]:
                return self.fail(404, "checkpoint unavailable")
            path = self.server.state / row["checkpoint_path"]
            if not path.is_file():
                return self.fail(503, "checkpoint file unavailable")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(path.stat().st_size))
            self.send_header("X-DP-Cursor", str(row["checkpoint_at"]))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)
            self.close_connection = True

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/v1/register":
            supplied = self.headers.get("X-Join-Token", "")
            if not supplied or not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(),
                                                        self.server.join_hash):
                return self.fail(401, "invalid join token")
            if self.headers.get("Content-Length") not in (None, "0"):
                return self.fail(400, "registration body is not used")
            with database(self.server.db_path) as db:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT MAX(id) FROM runs").fetchone()[0]
                run_id = max(self.server.start_id, (previous or 0) + 1)
                while run_id <= self.server.end_id and not self.server.registry.reserve(run_id):
                    run_id += 1
                if run_id > self.server.end_id:
                    return self.fail(503, "public run IDs exhausted")
                token = secrets.token_urlsafe(32)
                now = int(time.time())
                db.execute("INSERT INTO runs(id,token_sha256,created_at,last_seen) VALUES (?,?,?,?)",
                           (run_id, hashlib.sha256(token.encode()).hexdigest(), now, now))
            return self.respond(201, {"run_id": run_id, "token": token,
                                      "campaign": CAMPAIGN, "walk_id": WALK_ID,
                                      "dp_weight": DP_WEIGHT})
        match = RUN_PATH.fullmatch(parsed.path)
        if not match or match[2] not in ("dps", "checkpoint"):
            return self.fail(404, "unknown endpoint")
        run_id, suffix = int(match[1]), match[2]
        offsets = parse_qs(parsed.query).get("offset", [])
        if len(offsets) != 1 or not offsets[0].isdecimal():
            return self.fail(400, "one nonnegative offset is required")
        offset = int(offsets[0])
        with database(self.server.db_path) as db:
            row = self.authorized_run(db, run_id)
            if row is None:
                return self.fail(401, "invalid run token")
            try:
                data = self.body(MAX_BATCH_BYTES if suffix == "dps" else MAX_CHECKPOINT_BYTES)
                if suffix == "dps":
                    if offset % 32:
                        raise ValueError("DP offset must be a multiple of 32")
                    count = check_records(data, run_id)
                else:
                    if not data:
                        raise ValueError("empty checkpoint")
                    iterations = check_checkpoint(data, run_id)
            except ValueError as exc:
                return self.fail(400, str(exc))
            digest = hashlib.sha256(data).hexdigest()
            if suffix == "dps":
                prior = db.execute("SELECT sha256,size FROM batches WHERE run_id=? AND offset=?",
                                   (run_id, offset)).fetchone()
                if prior:
                    if prior["sha256"] == digest and prior["size"] == len(data):
                        return self.respond(200, {"ok": True, "duplicate": True,
                                                  "cursor": row["cursor"]})
                    return self.fail(409, "offset already holds different bytes")
                if offset != row["cursor"]:
                    return self.fail(409, "offset does not equal server cursor")
                relative = Path("batches") / str(run_id) / f"{offset:016d}-{digest}.bin"
                atomic_bytes(self.server.state / relative, data)
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT cursor FROM runs WHERE id=?", (run_id,)).fetchone()[0]
                if current != offset:
                    return self.fail(409, "concurrent upload advanced cursor")
                db.execute("INSERT INTO batches(run_id,offset,size,sha256,path,created_at) "
                           "VALUES (?,?,?,?,?,?)",
                           (run_id, offset, len(data), digest, str(relative), int(time.time())))
                db.execute("UPDATE runs SET cursor=?,last_seen=? WHERE id=?",
                           (offset + len(data), int(time.time()), run_id))
                return self.respond(201, {"ok": True, "records": count,
                                          "cursor": offset + len(data)})
            if offset != row["cursor"]:
                return self.fail(409, "checkpoint offset must equal DP cursor")
            relative = Path("checkpoints") / str(run_id) / f"{digest}.ck"
            atomic_bytes(self.server.state / relative, data)
            db.execute("UPDATE runs SET checkpoint_path=?,checkpoint_at=?,last_seen=? WHERE id=?",
                       (str(relative), offset, int(time.time()), run_id))
            return self.respond(201, {"ok": True, "sha256": digest,
                                      "iterations": iterations, "cursor": offset})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--run-id-start", type=int, required=True)
    parser.add_argument("--run-id-end", type=int, required=True)
    args = parser.parse_args(argv)
    join_token = os.environ.get("ECC_PUBLIC_JOIN_TOKEN", "")
    if len(join_token) < 24:
        parser.error("ECC_PUBLIC_JOIN_TOKEN must contain at least 24 characters")
    if not 1 <= args.run_id_start <= args.run_id_end <= 65535:
        parser.error("run ID range must fit in 1..65535")
    registry = S3Registry(os.environ.get("ECC_BUCKET", ""),
                          os.environ.get("ECC_PUBLIC_STREAM_ID", ""))
    registry.ready()
    server = Gateway((args.bind, args.port), args.state, args.run_id_start,
                     args.run_id_end, join_token, registry)
    print(f"gateway listening on {args.bind}:{args.port}; campaign={CAMPAIGN}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
