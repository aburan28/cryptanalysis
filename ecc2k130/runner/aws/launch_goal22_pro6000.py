#!/usr/bin/env python3
"""Launch one Runpod RTX PRO 6000 on the goal22 (~22 B it/s) table-walk client.

This is the fast kernel path. Do not use ``launch_opt_5090.py`` (sigma-fused
~5 B it/s) for collection. Requires CUDA 13 hosts
(``allowedCudaVersions=["13.0"]`` = driver 580+). Builds with nvcc 13.3.73 on
first boot if no prebuilt binary is in S3, then walks
``campaigns/ecc2k130-table8-22b-v1`` (DP34; separate from Certicom DP32).

Usage:
  RUNPOD_API_KEY=… AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… \\
    python3 ecc2k130/runner/aws/launch_goal22_pro6000.py [--from-pod ID]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REST = "https://rest.runpod.io/v1"
UA = "Mozilla/5.0 cryptanalysis-fleet/1.0"
CUDA13_VERSIONS = ["13.0"]
MIN_DRIVER_MAJOR = 580
KERNEL_PREFIX = "opt/pro6000-goal22"
ECC_PREFIX = "campaigns/ecc2k130-table8-22b-v1"
GPU_TYPE_IDS = [
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
]
START_WRAPPER = (
    "set -uo pipefail\n"
    'export DEBIAN_FRONTEND=noninteractive ECC_ROOT=/opt/ecc2k130 '
    'ECC_BUCKET="${ECC_BUCKET:-ecc2k130-590183823895}" '
    'AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}" PYTHONUNBUFFERED=1 '
    f'ECC_PREFIX="{ECC_PREFIX}"\n'
    "LOG=/tmp/ecc2k130-boot.log; touch \"$LOG\"; exec > >(tee -a \"$LOG\") 2>&1\n"
    'echo "wrapper $(date -u +%FT%TZ) host=$(hostname) kernel=pro6000-goal22"\n'
    "if ! command -v aws >/dev/null 2>&1; then "
    "apt-get update -qq || true; "
    "apt-get install -y -qq python3 python3-pip unzip curl ca-certificates || true; "
    "pip3 install -q awscli || true; fi\n"
    "if ! command -v aws >/dev/null 2>&1; then "
    "curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip; "
    "unzip -q /tmp/awscliv2.zip -d /tmp; /tmp/aws/install; fi\n"
    f'aws s3 cp "s3://$ECC_BUCKET/{KERNEL_PREFIX}/bootstrap.sh" '
    "/tmp/goal22-bootstrap.sh --only-show-errors\n"
    "bash /tmp/goal22-bootstrap.sh\n"
)


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def runpod(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        REST + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["RUNPOD_API_KEY"],
            "User-Agent": UA,
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def aws_env_from_pod(pod_id: str) -> dict:
    code, pod = runpod("GET", f"/pods/{pod_id}")
    if code >= 400 or not isinstance(pod, dict):
        die(f"could not read donor pod {pod_id}: {code} {pod}")
    env = dict(pod.get("env") or {})
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "ECC_BUCKET"):
        if not env.get(key):
            die(f"donor pod {pod_id} is missing {key}")
    return env


def ensure_aws(env: dict) -> str:
    os.environ["AWS_ACCESS_KEY_ID"] = env["AWS_ACCESS_KEY_ID"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = env["AWS_SECRET_ACCESS_KEY"]
    os.environ["AWS_DEFAULT_REGION"] = env.get("AWS_DEFAULT_REGION", "us-west-2")
    return env.get("ECC_BUCKET", "ecc2k130-590183823895")


def s3_cp(uri: str, dest: Path) -> None:
    subprocess.check_call(["aws", "s3", "cp", uri, str(dest), "--only-show-errors"])


def parse_driver(boot_text: str) -> str | None:
    for line in boot_text.splitlines():
        if line.startswith("NVIDIA GeForce RTX") or line.startswith("NVIDIA RTX"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[1][:1].isdigit():
                return parts[1]
    return None


def driver_ok(driver: str | None) -> bool:
    if not driver:
        return False
    try:
        return int(driver.split(".", 1)[0]) >= MIN_DRIVER_MAJOR
    except ValueError:
        return False


def create_pod(env: dict, name: str, country_codes=None, cloud_type: str = "SECURE"):
    body = {
        "name": name,
        "computeType": "GPU",
        "imageName": "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
        "cloudType": cloud_type,
        "containerDiskInGb": 80,
        "volumeInGb": 0,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "dockerEntrypoint": ["bash", "-c"],
        "dockerStartCmd": [START_WRAPPER],
        "env": {
            **{k: env[k] for k in env if k in (
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION",
                "ECC_BUCKET", "PUBLIC_KEY",
            )},
            "ECC_ALLOW_LEGACY_STORAGE": "1",
            "ECC_ALL_GPUS": "1",
            "ECC_CLAIM_NEW": "1",
            "ECC_SKIP_KERNEL_PIN": "1",
            "ECC_PREFIX": ECC_PREFIX,
            "ECC_ROOT": "/opt/ecc2k130",
            "ECC_BUCKET": env.get("ECC_BUCKET", "ecc2k130-590183823895"),
            "AWS_DEFAULT_REGION": env.get("AWS_DEFAULT_REGION", "us-west-2"),
            "PYTHONUNBUFFERED": "1",
        },
        "gpuTypeIds": list(GPU_TYPE_IDS),
        "gpuTypePriority": "custom",
        "gpuCount": 1,
        "allowedCudaVersions": list(CUDA13_VERSIONS),
    }
    if country_codes:
        body["countryCodes"] = country_codes
    return runpod("POST", "/pods", body)


def delete_pod(pod_id: str) -> None:
    code, _ = runpod("DELETE", f"/pods/{pod_id}")
    print(f"deleted {pod_id} ({code})")


def wait_boot(bucket: str, pod_id: str, known_hosts: set[str], timeout: int):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, meta = runpod("GET", f"/pods/{pod_id}")
        if code >= 400:
            time.sleep(5)
            continue
        listing = subprocess.check_output(
            ["aws", "s3", "ls", f"s3://{bucket}/logs/", "--recursive"], text=True
        )
        for line in listing.splitlines():
            if "boot.log" not in line or "runpod-" not in line:
                continue
            keypath = line.split()[-1]
            host = keypath.split("/")[1].replace("runpod-", "")
            if host in known_hosts:
                continue
            dest = Path("/tmp/goal22-launch-boot.log")
            try:
                s3_cp(f"s3://{bucket}/{keypath}", dest)
            except subprocess.CalledProcessError:
                continue
            text = dest.read_text(errors="replace")
            if "goal22-boot" not in text and "pro6000-goal22" not in text:
                continue
            if "NVIDIA" not in text and "driver" not in text:
                continue
            driver = parse_driver(text)
            print(f"  host={host} driver={driver} machine={(meta or {}).get('machineId')}")
            if "insufficient" in text or "driver below" in text:
                return False, host, driver, keypath, text
            if driver and not driver_ok(driver):
                return False, host, driver, keypath, text
            if driver_ok(driver):
                # Accept once CUDA gate passes; build may still be in progress.
                return True, host, driver, keypath, text
        time.sleep(10)
    return False, None, None, None, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--from-pod", default="", help="clone AWS/ECC env from this pod id")
    parser.add_argument("--seconds-wait", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=40)
    parser.add_argument("--cloud-type", default="SECURE", choices=["SECURE", "COMMUNITY"])
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()
    if "RUNPOD_API_KEY" not in os.environ:
        die("set RUNPOD_API_KEY")
    if not 1 <= args.count <= 4:
        die("count must be 1..4")

    if args.from_pod:
        env = aws_env_from_pod(args.from_pod)
    else:
        env = dict(os.environ)
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            if not env.get(key):
                die(f"set {key} or pass --from-pod")
    bucket = ensure_aws(env)

    receipt = {
        "kernel": KERNEL_PREFIX,
        "campaign_prefix": ECC_PREFIX,
        "profile": "rtx-pro6000-22b / goal22",
        "expected_rate_billion": 22.1,
        "cuda_policy": {
            "nvcc_min": "13.3",
            "runpod_allowedCudaVersions": CUDA13_VERSIONS,
            "min_driver_major": MIN_DRIVER_MAJOR,
        },
        "launched": [],
    }
    known_hosts: set[str] = set()
    launched = 0
    attempt = 0
    while launched < args.count and attempt < args.max_attempts:
        attempt += 1
        name = f"ecc2k-pro6000-goal22-{int(time.time())}"
        extras_cycle = [
            {"countryCodes": ["US", "CA"]},
            {"countryCodes": ["FR", "NL", "DE", "SE", "GB", "BE"]},
            {},
        ][(attempt - 1) % 3]
        cloud = args.cloud_type if attempt <= 6 else (
            "COMMUNITY" if args.cloud_type == "SECURE" else "SECURE"
        )
        print(f"attempt {attempt}: create {name} cloud={cloud} extras={extras_cycle}")
        code, resp = create_pod(
            env, name, extras_cycle.get("countryCodes"), cloud_type=cloud
        )
        if code >= 400 or not isinstance(resp, dict) or not resp.get("id"):
            print(f"  create failed: {code} {str(resp)[:300]}")
            time.sleep(8)
            continue
        pod_id = resp["id"]
        time.sleep(4)
        _, meta = runpod("GET", f"/pods/{pod_id}")
        machine = (meta or {}).get("machineId") if isinstance(meta, dict) else None
        print(f"  created {pod_id} machine={machine} cost={resp.get('costPerHr')}")
        ok, host, driver, logkey, text = wait_boot(
            bucket, pod_id, known_hosts, timeout=args.seconds_wait
        )
        if host:
            known_hosts.add(host)
        if not ok:
            print(f"  reject host={host} driver={driver}; deleting")
            delete_pod(pod_id)
            time.sleep(2)
            continue
        print(f"  accept host={host} driver={driver} (CUDA 13.3-capable)")
        row = {
            "id": pod_id,
            "name": (meta or {}).get("name") if isinstance(meta, dict) else name,
            "machineId": machine,
            "host": host,
            "driver": driver,
            "costPerHr": resp.get("costPerHr"),
            "log": logkey,
            "allowedCudaVersions": CUDA13_VERSIONS,
            "ecc_prefix": ECC_PREFIX,
            "cloudType": cloud,
        }
        receipt["launched"].append(row)
        launched += 1

    if launched < args.count:
        die(f"only launched {launched}/{args.count} CUDA 13.3-capable PRO 6000 workers", 2)
    out = args.receipt or Path(
        f"ecc2k130/runner/research/production/"
        f"{time.strftime('%Y-%m-%d')}-goal22-pro6000-launch.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
