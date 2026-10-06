"""Read campaign configuration, leases and checkpoint headers before a rollout."""
import json
import os
from pathlib import Path
import modal

LOCAL = Path(__file__).resolve().parent
if modal.is_local():
    import modal_worker as production
    inventory_image = production.check_image
else:
    inventory_image = None
app = modal.App("ecc2k130-deployment-inventory")


@app.function(image=inventory_image, timeout=300,
              secrets=[modal.Secret.from_name(os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud"))])
def inventory():
    import boto3
    import datetime
    import struct
    import re
    from concurrent.futures import ThreadPoolExecutor
    from botocore.exceptions import ClientError
    from botocore.config import Config
    s3 = boto3.client("s3", config=Config(connect_timeout=10, read_timeout=20, max_pool_connections=16,
                                        retries={"max_attempts": 1}))
    bucket = os.environ["ECC_BUCKET"]

    def listing(prefix, delimiter=None):
        args = {"Bucket": bucket, "Prefix": prefix}
        if delimiter:
            args["Delimiter"] = delimiter
        yield from s3.get_paginator("list_objects_v2").paginate(**args)

    print("Listing campaign namespaces", flush=True)
    prefixes = [""] + [p["Prefix"] for page in listing("campaigns/", "/")
                       for p in page.get("CommonPrefixes", [])]
    print(json.dumps({"prefixes": prefixes}), flush=True)
    result = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "bucket": bucket, "campaigns": [], "observed_run_ids": []}
    run_ids = set()
    for prefix in prefixes:
        print(json.dumps({"checking": prefix}), flush=True)
        try:
            cfg = json.loads(s3.get_object(Bucket=bucket, Key=prefix + "campaign.json")["Body"].read())
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                continue
            raise
        row = {"prefix": prefix.rstrip("/"), "config": {k: cfg.get(k) for k in
               ("curve", "campaignId", "walkId", "dpWeight", "batch", "blockThreads", "minBlocks",
                "workers", "runIdBase", "binarySha256")}, "leases": [], "checkpoints": []}
        base = int(cfg.get("runIdBase", 1))
        run_ids.add(base)
        for page in listing(prefix + "slots/"):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".json"):
                    continue
                slot = int(Path(obj["Key"]).stem.split("-")[1])
                run_ids.add(base + slot)
                row["leases"].append({"slot": slot, "configured_run_id": base + slot})
        latest = {}
        total = 0
        for page in listing(prefix + "ckpt/"):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".ck") or obj["Size"] < 40:
                    continue
                total += 1
                match = re.search(r"slot-\d+", obj["Key"])
                identity = match.group() if match else obj["Key"]
                if identity not in latest or obj["LastModified"] > latest[identity]["LastModified"]:
                    latest[identity] = obj
        row["checkpoint_objects"] = total
        print(json.dumps({"prefix": prefix, "checkpoint_objects": total,
                          "latest_per_slot": len(latest)}), flush=True)
        def read_header(obj):
            data = s3.get_object(Bucket=bucket, Key=obj["Key"], Range="bytes=0-39")["Body"].read()
            magic, version, curve, workers, batch, lanes, run_id, iteration = struct.unpack("<8s6IQ", data)
            if magic != b"ECC2K130":
                raise ValueError("unrecognized checkpoint header")
            return {"key": obj["Key"], "run_id": run_id, "version": version,
                "curve": curve, "workers": workers, "batch": batch, "lanes": lanes,
                "iteration": iteration, "updated_at": obj["LastModified"].isoformat()}
        with ThreadPoolExecutor(max_workers=16) as pool:
            row["checkpoints"] = list(pool.map(read_header, latest.values()))
        run_ids.update(ck["run_id"] for ck in row["checkpoints"])
        result["campaigns"].append(row)
    result["observed_run_ids"] = sorted(run_ids)
    return result


@app.local_entrypoint()
def main(output: str = "build/deployment-inventory.json"):
    path = LOCAL / output
    path.parent.mkdir(parents=True, exist_ok=True)
    result = inventory.remote()
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": str(path), "observed_run_ids": result["observed_run_ids"],
                      "campaigns": [r["prefix"] for r in result["campaigns"]]}))
