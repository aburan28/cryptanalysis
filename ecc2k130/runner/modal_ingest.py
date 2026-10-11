"""Dashboard ingester on Modal: modal run --detach ecc2k130/runner/modal_ingest.py"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import modal

SECRET = os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud")
STATUS_BUCKET = os.environ.get("ECC_STATUS_BUCKET", "ecc2k130-status-590183823895")
if modal.is_local():
    import modal_worker as production
    ingest_image = production.check_image
else:
    ingest_image = None
app = modal.App("ecc2k130-dp-ingest")


def supervise(command, env, stop_at):
    """Run the ingester until stop_at, restarting it after an exit as the Runpod boot loop does."""
    while time.time() < stop_at:
        process = subprocess.Popen(command, env=env)
        try:
            code = process.wait(timeout=max(1.0, stop_at - time.time()))
        except subprocess.TimeoutExpired:
            # dp_ingest.py treats SIGINT as a clean stop and ends its publisher thread.
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return
        print(json.dumps({"ingest_exit": code}), flush=True)
        time.sleep(15)


@app.function(image=ingest_image, cpu=1, memory=2048, timeout=86400, max_containers=1,
              retries=modal.Retries(max_retries=3, backoff_coefficient=1.0, initial_delay=60.0),
              secrets=[modal.Secret.from_name(SECRET)])
def ingest(seconds: int, deadline: float, rollout: str, status_bucket: str):
    import hashlib
    import boto3
    sys.path.insert(0, "/opt/ecc2k130/aws")
    import rds_network
    seconds = min(seconds, int(deadline - time.time()))
    if seconds < 1:
        print(json.dumps({"skipped": "deadline passed"}), flush=True)
        return
    bucket = os.environ["ECC_BUCKET"]
    # The Runpod ingest pod boots from this object too, so both hosts run one reviewed copy.
    code = boto3.client("s3").get_object(Bucket=bucket, Key="aws/dp_ingest.py")["Body"].read()
    script = Path("/tmp/dp_ingest.py")
    script.write_bytes(code)
    env = dict(os.environ, DATABASE_URL=os.environ.get("RHO_DP_DSN") or os.environ["DATABASE_URL"])
    try:
        print(json.dumps({"network": rds_network.ensure_access(rollout),
                          "dp_ingest_sha256": hashlib.sha256(code).hexdigest()}), flush=True)
        supervise([sys.executable, "-u", str(script), "--bucket", bucket, "--status-bucket", status_bucket,
                   "--threads", "6", "--status-every", "180", "--metric-namespace", "ECC2K130/Ingest"],
                  env, time.time() + seconds)
    finally:
        print(json.dumps({"removed_network_rules": rds_network.cleanup(rollout)}), flush=True)


@app.local_entrypoint()
def main(seconds: int = 82800):
    if not 1 <= seconds <= 82800:
        raise ValueError("seconds must be between 1 and 82800")
    if not os.environ.get("ECC_RDS_SECURITY_GROUP"):
        raise ValueError("set ECC_RDS_SECURITY_GROUP so the ingester can reach the database")
    rollout = uuid.uuid4().hex
    # Spawned, like the fleet coordinator, so a lost launcher cannot cancel it.
    call = ingest.spawn(seconds, time.time() + seconds, rollout, STATUS_BUCKET)
    print(json.dumps({"ingest_call_id": call.object_id, "rollout": rollout,
                      "seconds": seconds, "status_bucket": STATUS_BUCKET}), flush=True)
    call.get()
