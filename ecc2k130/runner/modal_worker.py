"""Cloud worker: modal run ecc2k130/modal_worker.py --command smoke"""
import os
import json
from pathlib import Path
import subprocess
import uuid

import modal

LOCAL = Path(__file__).resolve().parent
GPU = os.environ.get("ECC_MODAL_GPU", "RTX-PRO-6000")
ARCH = os.environ.get("ECC_CUDA_ARCH", "120")
SECRET = os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud")
NETWORK = {"ECC_RDS_SECURITY_GROUP": os.environ["ECC_RDS_SECURITY_GROUP"]} if os.environ.get("ECC_RDS_SECURITY_GROUP") else {}
SEED_BASE_IMAGE = os.environ.get("ECC_SEED_BASE_IMAGE", "")
if SEED_BASE_IMAGE:
    # Apply supervisor checks while retaining the exact production client.
    image = (modal.Image.from_id(SEED_BASE_IMAGE)
        .env({"ECC_SEED_BASE_IMAGE": SEED_BASE_IMAGE, **NETWORK})
        .add_local_file(LOCAL / "aws" / "worker.py", "/opt/ecc2k130/aws/worker.py", copy=True)
        .add_local_file(LOCAL / "aws" / "seed_registry.py", "/opt/ecc2k130/aws/seed_registry.py", copy=True)
        .add_local_file(LOCAL / "cloud.py", "/opt/ecc2k130/cloud.py", copy=True))
else:
    image = modal.Image.from_dockerfile(
        LOCAL / "deploy" / "Dockerfile", context_dir=LOCAL,
        build_args={"CUDA_ARCH": ARCH},
    ).entrypoint([]).env(NETWORK)
check_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "ca-certificates")
    .pip_install_from_requirements(LOCAL / "deploy" / "requirements.txt")
    .run_commands("curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /tmp/rds-ca.pem")
    .env({"PGSSLROOTCERT": "/tmp/rds-ca.pem", "AWS_EC2_METADATA_DISABLED": "true",
          "ECC_PREFIX": "campaigns/ecc2k130-frobenius32-120k-v1", **NETWORK})
    .add_local_file(LOCAL / "cloud.py", "/opt/ecc2k130/cloud.py")
    .add_local_file(LOCAL / "build.json", "/opt/ecc2k130/build.json")
    .add_local_file(LOCAL / "aws" / "worker.py", "/opt/ecc2k130/aws/worker.py")
    .add_local_file(LOCAL / "aws" / "seed_registry.py", "/opt/ecc2k130/aws/seed_registry.py")
    .add_local_file(LOCAL / "aws" / "rds_gpu.py", "/opt/ecc2k130/aws/rds_gpu.py")
    .add_local_file(LOCAL / "aws" / "rds_network.py", "/opt/ecc2k130/aws/rds_network.py")
    .add_local_file(LOCAL / "aws" / "campaign.json", "/opt/ecc2k130/aws/campaign.json")
)
app = modal.App("cryptanalysis-ecc2k130-worker")


@app.function(image=check_image, timeout=180, max_containers=1,
              secrets=[modal.Secret.from_name(SECRET)])
def readiness(smoke_test: bool = False, s3_only: bool = False, initialize: bool = False):
    import sys
    sys.path.insert(0, "/opt/ecc2k130")
    import cloud
    from rds_network import ensure_access, cleanup
    os.environ.setdefault("ECC_ROOT", "/tmp/ecc2k130-readiness")
    if s3_only:
        os.environ.pop("RHO_DP_DSN", None)
        os.environ.pop("DATABASE_URL", None)
    required = ["ECC_BUCKET", "AWS_DEFAULT_REGION"]
    missing = [name for name in required if not os.environ.get(name)]
    if not s3_only and not (os.environ.get("RHO_DP_DSN") or os.environ.get("DATABASE_URL")):
        missing.append("RHO_DP_DSN or DATABASE_URL")
    if missing:
        raise ValueError("Cloud secret is missing: " + ", ".join(missing))
    network_token = uuid.uuid4().hex
    try:
        if not s3_only:
            print(json.dumps({"network": ensure_access(network_token)}), flush=True)
        supervisor = cloud.Worker(install_signals=False)
        if initialize:
            cloud.initialize_campaign(supervisor)
        supervisor.loadConfig()
        print(json.dumps({"campaign_geometry": {name: supervisor.cfg.get(name) for name in
              ("curve", "batch", "blockThreads", "minBlocks", "packed", "workers", "dpWeight")}}), flush=True)
        cloud.preflight(supervisor, s3_only=s3_only, check_client=False)
        result = cloud.smoke(supervisor, s3_only=s3_only) if smoke_test else {}
        return {"ok": True, **result}
    except cloud.ConfigurationError:
        raise
    except Exception as exc:
        raise RuntimeError("Cloud readiness failed (%s); check campaign bucket, RDS credentials and network access"
                           % type(exc).__name__) from None
    finally:
        if not s3_only:
            cleanup(network_token)


@app.function(image=image, gpu=GPU, cpu=4, memory=4096, timeout=86400, max_containers=4,
              secrets=[modal.Secret.from_name(SECRET)])
def worker(command: str, seconds: int, s3_only: bool, rollout: str = ""):
    import sys
    sys.path.insert(0, "/opt/ecc2k130/aws")
    from rds_network import ensure_access
    if command not in ("preflight", "smoke", "run"):
        raise ValueError("command must be preflight, smoke or run")
    if not s3_only:
        if not rollout:
            raise ValueError("use the fleet entrypoint so network rules have an owner")
        print(json.dumps({"network": ensure_access(rollout)}), flush=True)
    args = ["python3", "/opt/ecc2k130/cloud.py", command, "--seconds", str(seconds)]
    if s3_only:
        args.append("--s3-only")
    # The supervisor handles its own duration and final flush before Modal's
    # hard deadline. S3 holds checkpoints across container replacements.
    subprocess.run(args, check=True)


@app.function(image=check_image, timeout=86400, max_containers=1, cpu=0.125,
              secrets=[modal.Secret.from_name(SECRET)])
def fleet(count: int, seconds: int, s3_only: bool):
    """Keep lifecycle and network cleanup remote when the launcher disconnects."""
    if not 1 <= count <= 4 or not 1 <= seconds <= 82800:
        raise ValueError("fleet requires 1..4 workers and 1..82800 seconds")
    import sys
    sys.path.insert(0, "/opt/ecc2k130/aws")
    from rds_network import cleanup
    rollout = uuid.uuid4().hex
    calls = []
    failed = []
    try:
        for _ in range(count):
            calls.append(worker.spawn("run", seconds, s3_only, rollout))
        print(json.dumps({"submitted": len(calls), "seconds_per_worker": seconds,
                          "rollout": rollout, "call_ids": [c.object_id for c in calls]}), flush=True)
    finally:
        # Join already-submitted calls even if a later submission fails.
        for call in calls:
            try:
                call.get()
            except Exception:
                failed.append(call.object_id)
        if not s3_only:
            removed = cleanup(rollout)
            print(json.dumps({"removed_network_rules": removed}), flush=True)
    if failed:
        raise RuntimeError("Workers failed: " + ", ".join(failed))
    return {"completed": len(calls), "rollout": rollout}


@app.local_entrypoint()
def main(command: str = "preflight", seconds: int = 82800, s3_only: bool = False,
         count: int = 4):
    if command not in ("preflight", "smoke", "run") or not 1 <= seconds <= 82800:
        raise ValueError("invalid command or duration (1..82800 seconds)")
    if not 1 <= count <= 4:
        raise ValueError("count must be between 1 and 4")
    # Prove the service path once before starting any long GPU work.
    result = readiness.remote(command in ("smoke", "run"), s3_only, command in ("smoke", "run"))
    print(json.dumps({"readiness": result}), flush=True)
    if command != "run":
        return
    print(json.dumps(fleet.remote(count, seconds, s3_only)), flush=True)
