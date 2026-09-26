#!/usr/bin/env python3
"""Report GPU client distinguished points into the rho-dp RDS store.

The packed CUDA client appends 32-byte records (start seed, 192-bit orbit
key).  This adapter calls the existing report_dp() function so those points
share the ecc2k-130 collision table with the Type-II CPU walkers.  The walk
starting seed is stored in walk_seed (and also encoded as coefficient a so
two different seeds that meet are a collision).

Credentials: DATABASE_URL or RHO_DP_DSN.  Never commit them.

  python3 rds_gpu.py report --file dp.bin --worker gpu-slot-0
  python3 rds_gpu.py watch-s3 --bucket ecc2k130-ACCOUNT --prefix dp/
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
from pathlib import Path

RECORD = struct.Struct("<4Q")  # seed, k0, k1, k2
RECORD_BYTES = RECORD.size
CAMPAIGN = os.environ.get("RHO_CAMPAIGN", "ecc2k-130")
CURVE = "certicom-ecc2k-130"
# Same modulus the Type-II ingest uses so a/b bytea widths match.
COEFF_MOD = 1 << 131
ORDER_N = str((2 << 128) + 0x4D4FDD5703A3F269)
LEGACY_WALK = "certicom-ecc2k130-frobenius-v1"
REPORT_SQL = """SELECT is_new, is_collision, prior_a, prior_b, prior_worker, collision_id
                FROM report_dp(%s, %s, %s, %s, %s, %s, %s)"""


def coeffBytes(value, n=None):
    value = int(value)
    if n is not None:
        value %= n
        length = max(1, (n.bit_length() + 7) // 8)
        return value.to_bytes(length, "big")
    if value == 0:
        return b"\x00"
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def parseGpuRecord(blob):
    """Return (start_seed:int, point_key:bytes) from one 32-byte GPU record."""
    if len(blob) != RECORD_BYTES:
        raise ValueError("GPU DP record is %d bytes, want %d" % (len(blob), RECORD_BYTES))
    seed, k0, k1, k2 = RECORD.unpack(blob)
    return seed, struct.pack("<3Q", k0, k1, k2)


def iterGpuRecords(data, start=0):
    if start < 0 or start % RECORD_BYTES:
        raise ValueError("start must be a nonnegative multiple of 32")
    end = len(data) - (len(data) - start) % RECORD_BYTES
    for off in range(start, end, RECORD_BYTES):
        yield parseGpuRecord(data[off:off + RECORD_BYTES])


def resolveDsn(explicit=None):
    for cand in (explicit, os.environ.get("RHO_DP_DSN"), os.environ.get("DATABASE_URL")):
        if cand:
            return cand.strip()
    raise RuntimeError("set DATABASE_URL or RHO_DP_DSN")


class Store:
    def __init__(self, dsn=None):
        import psycopg
        self._conn = psycopg.connect(resolveDsn(dsn), autocommit=True, connect_timeout=10,
                                      options="-c statement_timeout=30000")

    def close(self):
        self._conn.close()

    def register(self, campaign=CAMPAIGN, *, dp_weight=34, walk_id=None):
        if campaign == "ecc2k-130":
            # This historical row predates explicit walk/weight metadata.
            # Validate the known contract without rewriting shared metadata.
            if dp_weight != 32 or walk_id != LEGACY_WALK:
                raise ValueError("ecc2k-130 requires the legacy Frobenius walk at DP32")
            with self._conn.cursor() as cur:
                cur.execute("SELECT curve_id, order_n, dp_mask_bits, meta FROM rho_campaigns WHERE campaign_id=%s", (campaign,))
                row = cur.fetchone()
            if row is None:
                raise ValueError("the existing ecc2k-130 campaign is missing")
            curve, order, mask, metadata = row
            metadata = metadata or {}
            if (curve != CURVE or str(order) != ORDER_N or mask not in (None, 32)
                    or metadata.get("walk_id") not in (None, LEGACY_WALK)
                    or metadata.get("dp_weight") not in (None, 32)
                    or metadata.get("format") != "ecc2k130-gpu-packed32"
                    or metadata.get("point_key") != "3xuint64-le orbit representative (x only)"):
                raise ValueError("existing ecc2k-130 campaign metadata is incompatible")
            return
        meta = json.dumps({
            "format": "ecc2k130-gpu-packed32",
            "point_key": "3xuint64-le orbit representative (x only)",
            "walk_seed": "GPU client starting seed (big-endian integer)",
            "coeff_encoding": "17-byte big-endian mod 2^131; a=start-seed, b=0",
            "walker": "ecc2k130 packed CUDA client",
            "dp_weight": dp_weight,
            "walk_id": walk_id,
        })
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rho_campaigns (campaign_id, curve_id, order_n, dp_mask_bits, meta)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (campaign_id) DO UPDATE SET
                  meta = rho_campaigns.meta || EXCLUDED.meta
                WHERE rho_campaigns.curve_id = EXCLUDED.curve_id
                  AND rho_campaigns.dp_mask_bits = EXCLUDED.dp_mask_bits
                  AND (rho_campaigns.meta->>'walk_id') IS NOT DISTINCT FROM
                      (EXCLUDED.meta->>'walk_id')
                RETURNING campaign_id
                """,
                (campaign, CURVE, ORDER_N, dp_weight, meta),
            )
            if cur.fetchone() is None:
                raise ValueError("RDS campaign curve, DP weight or walk identity differs")

    def report(self, point_key, start_seed, *, campaign=CAMPAIGN, worker_id=None, steps=None):
        walk_seed = coeffBytes(start_seed)
        a = coeffBytes(start_seed, COEFF_MOD)
        b = coeffBytes(0, COEFF_MOD)
        with self._conn.cursor() as cur:
            cur.execute(
                REPORT_SQL,
                (campaign, point_key, a, b, walk_seed, steps, worker_id),
            )
            row = cur.fetchone()
        return {
            "is_new": bool(row[0]),
            "is_collision": bool(row[1]),
            "prior_worker": row[4],
            "collision_id": int(row[5]) if row[5] is not None else None,
            "walk_seed_hex": walk_seed.hex(),
        }

    def report_many(self, records, *, campaign=CAMPAIGN, worker_id=None):
        """Bounded pipelining avoids a network round trip per GPU record."""
        pending = []
        try:
            with self._conn.pipeline() as pipeline:
                for point_key, seed in records:
                    walk_seed = coeffBytes(seed)
                    cur = self._conn.execute(REPORT_SQL, (campaign, point_key,
                        coeffBytes(seed, COEFF_MOD), coeffBytes(0, COEFF_MOD),
                        walk_seed, None, worker_id))
                    pending.append((cur, walk_seed))
                pipeline.sync()
            result = []
            for cur, walk_seed in pending:
                row = cur.fetchone()
                result.append({"is_new": bool(row[0]), "is_collision": bool(row[1]),
                    "prior_worker": row[4], "collision_id": int(row[5]) if row[5] is not None else None,
                    "walk_seed_hex": walk_seed.hex()})
            return result
        finally:
            for cur, _ in pending:
                cur.close()


def reportGpuDelta(path, *, worker_id, campaign=CAMPAIGN, dsn=None, start=0, progress=None, dp_weight=34, walk_id=None):
    """Report every whole GPU record in path. Returns {reported, new, collisions}."""
    if start < 0 or start % RECORD_BYTES:
        raise ValueError("start must be a nonnegative multiple of 32")
    store = Store(dsn)
    try:
        store.register(campaign, dp_weight=dp_weight, walk_id=walk_id)
        reported = new = collisions = 0
        last = None
        with open(path, "rb") as source:
            source.seek(start)
            while True:
                blob = source.read(RECORD_BYTES * 256)
                if len(blob) < RECORD_BYTES:
                    break
                records = []
                for seed, key in iterGpuRecords(blob):
                    if progress is not None:
                        progress()
                    records.append((key, seed))
                results = store.report_many(records, campaign=campaign, worker_id=worker_id)
                if len(results) != len(records):
                    raise RuntimeError("RDS returned incomplete batch accounting")
                if progress is not None:
                    progress()
                for out in results:
                    reported += 1
                    if out["is_new"]:
                        new += 1
                    if out["is_collision"]:
                        collisions += 1
                        last = out
        return {"reported": reported, "new": new, "collisions": collisions, "last_collision": last}
    finally:
        store.close()


def cmd_report(args):
    stats = reportGpuDelta(args.file, worker_id=args.worker, campaign=args.campaign,
                           dsn=args.dsn, start=args.start, dp_weight=args.dp_weight, walk_id=args.walk_id)
    print(json.dumps({"ok": True, **stats, "worker": args.worker}))
    return 0


def cmd_watch_s3(args):
    import boto3
    store = Store(args.dsn)
    store.register(args.campaign, dp_weight=args.dp_weight, walk_id=args.walk_id)
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.is_file() else {"keys": {}}
    total = {"reported": 0, "new": 0, "collisions": 0}
    try:
        while True:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=args.bucket, Prefix=args.prefix):
                for obj in page.get("Contents") or []:
                    key = obj["Key"]
                    size = int(obj["Size"])
                    seen = int(state["keys"].get(key, 0))
                    if size <= seen:
                        continue
                    body = s3.get_object(Bucket=args.bucket, Key=key, Range="bytes=%d-" % seen)["Body"].read()
                    whole = len(body) - len(body) % RECORD_BYTES
                    worker = args.worker or key.replace("/", "-")
                    for seed, pk in iterGpuRecords(body[:whole]):
                        out = store.report(pk, seed, campaign=args.campaign, worker_id=worker)
                        total["reported"] += 1
                        if out["is_new"]:
                            total["new"] += 1
                        if out["is_collision"]:
                            total["collisions"] += 1
                            print(json.dumps({"event": "collision", "key": key, **out}), flush=True)
                    state["keys"][key] = seen + whole
                    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"ok": True, **total, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
                  flush=True)
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
    finally:
        store.close()


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dsn", default=None)
    p.add_argument("--campaign", default=CAMPAIGN)
    p.add_argument("--dp-weight", type=int, default=32)
    p.add_argument("--walk-id", default=LEGACY_WALK)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="ingest one local GPU dp.bin / delta")
    r.add_argument("--file", required=True)
    r.add_argument("--worker", required=True)
    r.add_argument("--start", type=int, default=0)
    r.set_defaults(func=cmd_report)
    w = sub.add_parser("watch-s3", help="tail s3://bucket/prefix GPU deltas into RDS")
    w.add_argument("--bucket", required=True)
    w.add_argument("--prefix", default="dp/")
    w.add_argument("--state", default=".rds_gpu_s3_state.json")
    w.add_argument("--worker", default=None)
    w.add_argument("--poll-seconds", type=float, default=15)
    w.add_argument("--once", action="store_true")
    w.set_defaults(func=cmd_watch_s3)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
