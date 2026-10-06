#!/usr/bin/env python3
"""Rent a Runpod pod for the F4 benchmarks, run commands on it, and give it back.

    runpod_bench.py up f4-gpu --gpu "NVIDIA GeForce RTX 5090" --min-vcpu 16
    runpod_bench.py up f4-cpu --cpu 32
    runpod_bench.py sync f4-gpu                  # this checkout, edits included
    runpod_bench.py ssh f4-gpu -- 'nvidia-smi'
    runpod_bench.py fetch f4-gpu REMOTE_PATH LOCAL_DIR
    runpod_bench.py down f4-gpu

Needs RUNPOD_API_KEY.  SSH uses ~/.ssh/id_ed25519: the pod receives that
key, beside the account's registered ones, through its PUBLIC_KEY variable,
so nothing is added to the account.  Every pod stops itself after
--max-hours (default 6) through the pod-scoped key Runpod injects, in case
nobody runs `down`.  Pods are found by name; `up` refuses a name in use.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "cloud"))

REST = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
KEY = Path.home() / ".ssh" / "id_ed25519"
REMOTE = "/root/cryptanalysis"
GPU_IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
CPU_IMAGE = "runpod/base:1.0.2-ubuntu2404"

# PID 1: a lifetime cap that stops the pod, then the image's /start.sh, which
# installs PUBLIC_KEY and starts sshd.
STAGE0 = r"""
( sleep "$F4_MAX_SECONDS"
  curl -s https://api.runpod.io/graphql -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id } }\"}"
) >/tmp/f4-lifetime.log 2>&1 &
[ -x /start.sh ] && exec /start.sh
exec sleep infinity
""".strip()


def api(method, url, body=None, timeout=60):
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        sys.exit("RUNPOD_API_KEY is not set")
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "cryptanalysis-f4-bench/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as err:
        sys.exit(f"{method} {url}: HTTP {err.code}: {err.read().decode(errors='replace')[:600]}")
    return json.loads(raw) if raw.strip() else None


def pods():
    out = api("GET", f"{REST}/pods")
    return out if isinstance(out, list) else out.get("pods", [])


def find(name):
    live = [p for p in pods() if p.get("name") == name and p.get("desiredStatus") != "TERMINATED"]
    return live[0] if live else None


def need(name):
    pod = find(name)
    if pod is None:
        sys.exit(f"no pod named {name}")
    return pod


def public_keys():
    out = api("POST", GRAPHQL, {"query": "query { myself { pubKey } }"})
    keys = (out["data"]["myself"].get("pubKey") or "").splitlines()
    keys.append(Path(f"{KEY}.pub").read_text().strip())
    seen, kept = set(), []
    for key in (k.strip() for k in keys if k.strip()):
        body = " ".join(key.split()[:2])
        if body not in seen:
            seen.add(body)
            kept.append(key)
    return "\n".join(kept)


def ssh_args(pod):
    port = (pod.get("portMappings") or {}).get("22")
    if not pod.get("publicIp") or not port:
        sys.exit(f"{pod['name']}: no public ssh port yet")
    return ["ssh", "-i", str(KEY), "-p", str(port), "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
            "-o", "ServerAliveInterval=30", f"root@{pod['publicIp']}"]


def cmd_up(args):
    if find(args.name):
        sys.exit(f"a pod named {args.name} exists; `down` it first")
    if not KEY.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(KEY)], check=True)
    body = {
        "name": args.name, "cloudType": args.cloud, "containerDiskInGb": args.disk,
        "volumeInGb": 0, "ports": ["22/tcp"], "dockerEntrypoint": ["bash", "-c"],
        "dockerStartCmd": [STAGE0],
        "env": {"PUBLIC_KEY": public_keys(), "F4_MAX_SECONDS": str(int(args.max_hours * 3600))},
    }
    if args.cpu:
        body.update(computeType="CPU", imageName=args.image or CPU_IMAGE,
                    cpuFlavorIds=args.cpu_flavor, cpuFlavorPriority="custom", vcpuCount=args.cpu)
    else:
        body.update(computeType="GPU", imageName=args.image or GPU_IMAGE, gpuTypeIds=args.gpu,
                    gpuTypePriority="custom", gpuCount=args.gpu_count,
                    minVCPUPerGPU=args.min_vcpu, minRAMPerGPU=args.min_ram,
                    allowedCudaVersions=["13.0", "12.9", "12.8"])
    pod = api("POST", f"{REST}/pods", body)
    print(f"created {pod['id']} ({pod.get('costPerHr')} $/hr); waiting for ssh", flush=True)
    deadline = time.time() + args.wait
    while time.time() < deadline:
        pod = api("GET", f"{REST}/pods/{pod['id']}")
        if pod.get("publicIp") and (pod.get("portMappings") or {}).get("22"):
            probe = subprocess.run([*ssh_args(pod), "-o", "ConnectTimeout=10", "true"],
                                   capture_output=True)
            if probe.returncode == 0:
                print(json.dumps({k: pod.get(k) for k in ("id", "name", "publicIp", "portMappings",
                                  "vcpuCount", "memoryInGb", "costPerHr", "imageName")}))
                return 0
        time.sleep(10)
    sys.exit(f"{pod['id']}: ssh not up after {args.wait} s; the pod is kept (`down` removes it)")


def cmd_ssh(args):
    command = " ".join(args.command) if args.command else None
    return subprocess.run([*ssh_args(need(args.name)), *([command] if command else [])]).returncode


def cmd_sync(args):
    import tree
    data, summary = tree.pack(REPO)
    target = args.dest or REMOTE
    print(f"shipping {summary['files']} files, {summary['bytes'] / 1e6:.1f} MB to {target}", flush=True)
    script = f"mkdir -p {target} && tar --no-same-owner -xzf - -C {target}"
    return subprocess.run([*ssh_args(need(args.name)), script], input=data).returncode


def cmd_fetch(args):
    Path(args.local).mkdir(parents=True, exist_ok=True)
    pack = subprocess.Popen([*ssh_args(need(args.name)),
                             f"tar -czf - -C $(dirname {args.remote}) $(basename {args.remote})"],
                            stdout=subprocess.PIPE)
    unpack = subprocess.run(["tar", "-xzf", "-", "-C", args.local], stdin=pack.stdout)
    pack.wait()
    return pack.returncode or unpack.returncode


def cmd_down(args):
    pod = need(args.name)
    api("DELETE", f"{REST}/pods/{pod['id']}")
    print(f"deleted {pod['id']} ({args.name})")
    return 0


def cmd_list(args):
    for pod in pods():
        print(f"{pod['id']}  {pod.get('name')}  {pod.get('desiredStatus')}  "
              f"{pod.get('vcpuCount')} vCPU  {pod.get('costPerHr')} $/hr  {pod.get('imageName')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up")
    up.add_argument("name")
    up.add_argument("--gpu", action="append", default=[], metavar="GPU_TYPE_ID",
                    help="acceptable GPU types, in order of preference")
    up.add_argument("--gpu-count", type=int, default=1)
    up.add_argument("--min-vcpu", type=int, default=16, help="vCPUs per GPU")
    up.add_argument("--min-ram", type=int, default=32, help="GB per GPU")
    up.add_argument("--cpu", type=int, default=0, help="a CPU pod with this many vCPUs")
    up.add_argument("--cpu-flavor", action="append", default=None)
    up.add_argument("--cloud", default="SECURE", choices=["SECURE", "COMMUNITY"])
    up.add_argument("--image")
    up.add_argument("--disk", type=int, default=40)
    up.add_argument("--max-hours", type=float, default=6.0)
    up.add_argument("--wait", type=int, default=900)
    ssh = sub.add_parser("ssh")
    ssh.add_argument("name")
    ssh.add_argument("command", nargs=argparse.REMAINDER)
    sync = sub.add_parser("sync")
    sync.add_argument("name")
    sync.add_argument("--dest")
    fetch = sub.add_parser("fetch")
    fetch.add_argument("name")
    fetch.add_argument("remote")
    fetch.add_argument("local")
    down = sub.add_parser("down")
    down.add_argument("name")
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "up":
        if args.cpu and args.gpu:
            sys.exit("--cpu and --gpu are exclusive")
        if not args.cpu and not args.gpu:
            sys.exit("pass --gpu TYPE (repeatable) or --cpu N")
        args.cpu_flavor = args.cpu_flavor or ["cpu5c", "cpu3c"]
    if args.cmd == "ssh" and args.command[:1] == ["--"]:
        args.command = args.command[1:]
    return {"up": cmd_up, "ssh": cmd_ssh, "sync": cmd_sync, "fetch": cmd_fetch,
            "down": cmd_down, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
