"""Read leases, checkpoints and indexed RDS sample records; no GPU allocation."""
import json
import os
from pathlib import Path
import modal

if modal.is_local():
    import modal_worker as production
    verification_image = production.check_image
else:
    verification_image = None
app = modal.App("ecc2k130-production-verification")


@app.function(image=verification_image, timeout=240,
              secrets=[modal.Secret.from_name(os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud"))])
def verify(prefix: str, campaign: str):
    import datetime
    import struct
    import sys
    import time
    import uuid
    import boto3
    import psycopg
    sys.path.insert(0, "/opt/ecc2k130/aws")
    import rds_network
    token = uuid.uuid4().hex
    result = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "campaign": campaign, "prefix": prefix, "slots": []}
    try:
        rds_network.ensure_access(token)
        s3 = boto3.client("s3")
        bucket = os.environ["ECC_BUCKET"]
        objects = [o for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix + "/")
                   for o in p.get("Contents", [])]
        by_key = {o["Key"]: o for o in objects}
        with psycopg.connect(os.environ.get("RHO_DP_DSN") or os.environ["DATABASE_URL"],
                            connect_timeout=10, options="-c statement_timeout=15000 -c default_transaction_read_only=on") as db:
            for obj in objects:
                if not obj["Key"].startswith(prefix + "/slots/"):
                    continue
                slot = int(Path(obj["Key"]).stem.split("-")[1])
                lease = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                row = {"slot": slot, **lease, "lease_current": lease.get("leaseUntil", 0) > time.time()}
                ck = by_key.get(f"{prefix}/ckpt/slot-{slot:05d}.ck")
                if ck:
                    blob = s3.get_object(Bucket=bucket, Key=ck["Key"], Range="bytes=0-39")["Body"].read()
                    magic, version, curve, threads, batch, lanes, run_id, iteration = struct.unpack("<8s6IQ", blob)
                    row["checkpoint"] = {"version": version, "curve": curve, "threads": threads,
                        "batch": batch, "run_id": run_id, "iteration": iteration,
                        "updated_at": ck["LastModified"].isoformat(), "bytes": ck["Size"]}
                deltas = [o for o in objects if o["Key"].startswith(f"{prefix}/dp/slot-{slot:05d}/") and o["Size"] >= 32]
                row["s3_delta_records"] = sum(o["Size"] // 32 for o in deltas)
                if deltas:
                    latest = max(deltas, key=lambda o: o["LastModified"])
                    blob = s3.get_object(Bucket=bucket, Key=latest["Key"], Range="bytes=0-31")["Body"].read()
                    seed = struct.unpack_from("<Q", blob)[0]
                    stored = db.execute("SELECT a, worker_id, found_at FROM distinguished_points WHERE campaign_id=%s AND point_key=%s",
                                        (campaign, blob[8:32])).fetchone()
                    row["rds_sample_present"] = bool(stored)
                    row["rds_sample_seed_matches"] = bool(stored and int.from_bytes(stored[0], "big") == seed)
                    if stored:
                        row["rds_sample_worker"] = stored[1]
                        row["rds_sample_found_at"] = stored[2].isoformat()
                result["slots"].append(row)
    finally:
        result["removed_network_rules"] = rds_network.cleanup(token)
    return result


@app.local_entrypoint()
def main(prefix: str = "campaigns/ecc2k130-frobenius32-120k-v1", campaign: str = "ecc2k-130",
         output: str = "build/frobenius32-120k-live.json"):
    path = Path(__file__).resolve().parent / output
    path.parent.mkdir(parents=True, exist_ok=True)
    result = verify.remote(prefix, campaign)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
