#!/usr/bin/env python3
"""Feed durable, invited contributor batches into the existing RDS collision pool.

Records remain marked as unverified until an independent seed replay.  The
ingester is deliberately separate from the HTTPS gateway: database downtime
cannot turn an accepted upload into lost work.
"""

from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aws"))
from rds_gpu import Store, parseGpuRecord  # noqa: E402
from protocol import CAMPAIGN, DP_WEIGHT, WALK_ID, check_records  # noqa: E402
from seed_registry import S3Registry  # noqa: E402
from server import database  # noqa: E402


def check_gateway_identity(state: Path, bucket: str, stream_id: str) -> None:
    with database(state / "gateway.sqlite3") as db:
        config = dict(db.execute("SELECT key,value FROM config WHERE key IN ('bucket','stream_id')"))
    if config != {"bucket": bucket, "stream_id": stream_id}:
        raise RuntimeError("ingester and gateway seed/archive identity differ")


def process_one(state: Path, store: Store) -> dict | None:
    with database(state / "gateway.sqlite3") as db:
        row = db.execute("SELECT * FROM batches WHERE ingested_at IS NULL ORDER BY id LIMIT 1").fetchone()
    if row is None:
        return None
    path = state / row["path"]
    if path.is_file():
        body = path.read_bytes()
    else:
        registry = S3Registry(os.environ["ECC_BUCKET"], os.environ["ECC_PUBLIC_STREAM_ID"])
        body = registry.fetch_batch(row["run_id"], row["offset"], row["sha256"], row["size"])
    if len(body) != row["size"]:
        raise RuntimeError(f"batch {row['id']} has a truncated durable file")
    import hashlib
    if hashlib.sha256(body).hexdigest() != row["sha256"]:
        raise RuntimeError(f"batch {row['id']} has a mismatched durable digest")
    check_records(body, row["run_id"])
    reported = new_points = collisions = 0
    found = []
    for begin in range(0, len(body), 256 * 32):
        records = [parseGpuRecord(body[pos:pos + 32])
                   for pos in range(begin, min(begin + 256 * 32, len(body)), 32)]
        results = store.report_many([(key, seed) for seed, key in records],
                                    campaign=CAMPAIGN,
                                    worker_id=f"public-run-{row['run_id']}:unverified")
        if len(results) != len(records):
            raise RuntimeError("RDS returned incomplete batch accounting")
        for index, ((seed, key), result) in enumerate(zip(records, results)):
            reported += 1
            new_points += int(result["is_new"])
            collisions += int(result["is_collision"])
            if result["is_collision"]:
                found.append((row["id"], begin // 32 + index, str(seed), key.hex(),
                              result["collision_id"], result["prior_worker"]))
    with database(state / "gateway.sqlite3") as db:
        db.execute("BEGIN IMMEDIATE")
        for item in found:
            db.execute("INSERT OR IGNORE INTO collision_records "
                       "(batch_id,index_in_batch,seed,point_key_hex,collision_id,prior_worker) "
                       "VALUES (?,?,?,?,?,?)", item)
        db.execute("UPDATE batches SET ingested_at=?,reported=?,new_points=?,collisions=? "
                   "WHERE id=? AND ingested_at IS NULL",
                   (int(time.time()), reported, new_points, collisions, row["id"]))
        db.commit()
    # The S3 object was written before the gateway acknowledged this batch.
    # Local files are only a staging cache once RDS has committed the report.
    path.unlink(missing_ok=True)
    return {"batch_id": row["id"], "run_id": row["run_id"], "reported": reported,
            "new_points": new_points, "collisions": collisions}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if os.environ.get("ECC_LIVE_INGEST") != "1":
        parser.error("set ECC_LIVE_INGEST=1 only after the gateway and run-ID range are validated")
    lock_path = args.state / "ingest.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    check_gateway_identity(args.state, os.environ.get("ECC_BUCKET", ""),
                           os.environ.get("ECC_PUBLIC_STREAM_ID", ""))
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = Store()
        try:
            store.register(CAMPAIGN, dp_weight=DP_WEIGHT, walk_id=WALK_ID)
            while True:
                result = process_one(args.state, store)
                if result:
                    print(result, flush=True)
                elif args.once:
                    return 0
                else:
                    time.sleep(2)
        finally:
            store.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Driver exceptions may contain DSNs. Print only a safe class name.
        print(f"public DP ingest stopped ({type(exc).__name__}); raw batches retained", file=sys.stderr)
        raise SystemExit(1)
