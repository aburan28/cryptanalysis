"""One-pod RunPod controller for the isolated ECC2K-130 benchmark.

The API key is read without echo and never written to a file or sent to the pod.
"""
import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

BASE = "https://rest.runpod.io/v1"
DEFAULT_NAME = "ecc2k130-rho-pair-5090-20261015a"
GPU = "NVIDIA GeForce RTX 5090"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def request(key, method, path, body=None):
    encoded = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=encoded, method=method, headers={
        "Authorization": "Bearer " + key, "User-Agent": "cryptanalysis-rho-bench/1.0",
        **({"Content-Type": "application/json"} if encoded is not None else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            data = json.loads(raw)
        except ValueError:
            data = {"message": raw[:400]}
        return exc.code, data


def save(path, data):
    with path.open("x") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def safe_pod(pod):
    return {name: pod.get(name) for name in (
        "id", "name", "desiredStatus", "lastStatusChange", "machineId",
        "gpuCount", "gpuTypeId", "costPerHr", "createdAt", "runtime",
        "imageName", "cloudType", "allowedCudaVersions", "containerDiskInGb",
    ) if name in pod}


def body(public_key, cloud_type, name):
    boot = "\n".join([
        "set -euo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update -qq",
        "apt-get install -y -qq --no-install-recommends openssh-server python3 make g++ ca-certificates",
        "mkdir -p /run/sshd /root/.ssh",
        "printf '%s\\n' \"$PUBLIC_KEY\" > /root/.ssh/authorized_keys",
        "chmod 700 /root/.ssh",
        "chmod 600 /root/.ssh/authorized_keys",
        "exec /usr/sbin/sshd -D -e",
    ])
    return {
        "name": name, "computeType": "GPU", "imageName": "nvidia/cuda:13.3.1-devel-ubuntu24.04",
        "cloudType": cloud_type, "containerDiskInGb": 40, "volumeInGb": 0,
        "volumeMountPath": "/workspace", "ports": ["22/tcp"],
        "dockerEntrypoint": ["bash", "-lc"], "dockerStartCmd": [boot],
        "env": {"PUBLIC_KEY": public_key}, "gpuTypeIds": [GPU],
        "gpuTypePriority": "custom", "gpuCount": 1, "allowedCudaVersions": ["13.0"],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("create", "status", "delete"))
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--cloud", choices=("COMMUNITY", "SECURE"), default="COMMUNITY")
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--public-key", type=Path, default=Path.home() / ".ssh/id_ed25519.pub")
    a = p.parse_args()
    out = a.run_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    key = getpass.getpass("RunPod key: ")
    if a.action == "create":
        if (out / "runpod-create.json").exists():
            raise RuntimeError("create receipt already exists; never duplicate a pod")
        before_code, before = request(key, "GET", "/pods")
        if before_code != 200 or not isinstance(before, list):
            raise RuntimeError(f"pod inventory failed: HTTP {before_code}")
        if any(x.get("name") == a.name for x in before):
            raise RuntimeError("a pod with the benchmark name already exists")
        public_key = a.public_key.read_text().strip()
        if not public_key.startswith(("ssh-ed25519 ", "ssh-rsa ")):
            raise ValueError("invalid public key")
        req_body = body(public_key, a.cloud, a.name)
        started = stamp()
        code, response = request(key, "POST", "/pods", req_body)
        # A failed/ambiguous create is followed by inventory, never a create retry.
        after_code, after = request(key, "GET", "/pods")
        named = [safe_pod(x) for x in after if x.get("name") == a.name] if after_code == 200 and isinstance(after, list) else None
        receipt = {"started_at_utc": started, "completed_at_utc": stamp(),
                   "request": req_body, "create_http": code,
                   "create_response": (safe_pod(response) if code < 400 else response)
                       if isinstance(response, dict) else response,
                   "inventory_before_ids": [x.get("id") for x in before],
                   "inventory_after_http": after_code, "matching_after": named}
        save(out / "runpod-create.json", receipt)
        print(json.dumps({"create_http": code, "pod_id": response.get("id") if isinstance(response, dict) else None,
                          "matching_after": named,
                          "error": response if code >= 400 else None}), flush=True)
        return

    created = json.loads((out / "runpod-create.json").read_text())
    expected_name = created["request"]["name"]
    listed = created.get("matching_after") or []
    ids = {x.get("id") for x in listed if x.get("id")}
    direct = created.get("create_response", {}).get("id")
    if direct:
        ids.add(direct)
    if len(ids) != 1:
        raise RuntimeError("pod identity is not uniquely resolved")
    pod_id = next(iter(ids))
    if a.action == "status":
        code, pod = request(key, "GET", "/pods/" + pod_id)
        name = "runpod-status-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        data = {"at_utc": stamp(), "pod_id": pod_id, "http": code,
                "pod": safe_pod(pod) if code == 200 and isinstance(pod, dict) else pod}
        save(out / name, data)
        print(json.dumps(data), flush=True)
        return
    code, pod = request(key, "GET", "/pods/" + pod_id)
    if code != 200 or not isinstance(pod, dict) or pod.get("name") != expected_name:
        raise RuntimeError(f"pod identity/status mismatch: HTTP {code}")
    delete_code, delete_result = request(key, "DELETE", "/pods/" + pod_id)
    time.sleep(2)
    verify_code, verify = request(key, "GET", "/pods/" + pod_id)
    receipt = {"at_utc": stamp(), "pod_id": pod_id, "prior": safe_pod(pod),
               "delete_http": delete_code, "delete_response": delete_result,
               "verify_http": verify_code,
               "verify": safe_pod(verify) if verify_code == 200 and isinstance(verify, dict) else verify}
    save(out / "runpod-delete.json", receipt)
    print(json.dumps({"pod_id": pod_id, "delete_http": delete_code, "verify_http": verify_code}), flush=True)


if __name__ == "__main__":
    main()
