#!/usr/bin/env python3
"""Rent a Runpod GPU pod for one job, run it on this checkout, and give the pod back.

    cloud/runpod_pod.py run ic-gpu --out results/run.json -- \\
        'cd suite && cargo run --release --bin ca-ic -- run --degree 23 \\
         --curve-a 1 --json > ../results/run.json'

`run` creates the pod NAME unless it exists, ships this checkout (edits
included, as cloud/tree.py packs it) to /root/cryptanalysis, installs Rust
and NVRTC when they are missing (cloud/pod_env.sh), runs CMD there with
CA_NVRTC_LIB set, copies the --out paths back into this checkout, and
deletes the pod it created unless --keep.  Its exit status is CMD's.  The
pieces are commands too:

    cloud/runpod_pod.py up NAME [--gpu TYPE ...] [--min-vcpu N] | [--cpu N]
    cloud/runpod_pod.py sync NAME
    cloud/runpod_pod.py ssh NAME -- 'nvidia-smi'
    cloud/runpod_pod.py fetch NAME REMOTE_PATH LOCAL_DIR
    cloud/runpod_pod.py down NAME
    cloud/runpod_pod.py list

Needs RUNPOD_API_KEY.  SSH uses the key fleet.py uses (RUNPOD_SSH_KEY or
RUNPOD_SSH_PRIVATE_KEY) when one is set, else ~/.ssh/id_ed25519 (created if
missing): the pod receives its public half, beside the account's registered
keys, through its PUBLIC_KEY variable, so nothing is added to the account.
Every pod stops itself after --max-hours (default 6) through the pod-scoped
key Runpod injects, in case nobody deletes it.  Pods are found by name; `up`
refuses a name in use.  Without --gpu, a GPU pod takes the first of
DEFAULT_GPUS in stock with at least --min-vcpu vCPUs.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

REST = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
KEY = Path.home() / ".ssh" / "id_ed25519"
REMOTE = "/root/cryptanalysis"
GPU_IMAGE = "runpod/base:1.0.2-ubuntu2404"
CPU_IMAGE = "runpod/base:1.0.2-ubuntu2404"
DEFAULT_GPUS = [
    "NVIDIA GeForce RTX 5090",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    "NVIDIA H100 80GB HBM3",
]

# PID 1: a lifetime cap that stops the pod; the script in POD_BOOT_B64, if
# any, in the background (how cairn_queue.py makes a runner); then the
# image's /start.sh, which installs PUBLIC_KEY and starts sshd.
STAGE0 = r"""
( sleep "$POD_MAX_SECONDS"
  curl -s https://api.runpod.io/graphql -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id } }\"}"
) >/tmp/pod-lifetime.log 2>&1 &
if [ -n "${POD_BOOT_B64:-}" ]; then
  echo "$POD_BOOT_B64" | base64 -d >/root/pod-boot.sh
  setsid bash /root/pod-boot.sh >>/root/pod-boot.log 2>&1 </dev/null &
fi
[ -x /start.sh ] && exec /start.sh
exec sleep infinity
""".strip()

# Before CMD on the pod, in the shipped checkout: Rust and NVRTC when missing,
# and the variables the suite's CUDA paths read.
BOOTSTRAP = r"""
set -e
cd /root/cryptanalysis
source cloud/pod_env.sh
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/gpu: /' || true
echo "rustc: $(rustc --version)"
""".strip()


def api(method, url, body=None, timeout=60):
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        sys.exit("RUNPOD_API_KEY is not set (add it to Cursor Dashboard > Cloud Agents > Secrets)")
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "cryptanalysis-runpod-pod/1.0"})
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


def key_path():
    """The private key ssh uses: fleet.py's (RUNPOD_SSH_KEY, RUNPOD_SSH_PRIVATE_KEY)
    when one is set, else ~/.ssh/id_ed25519, created if missing."""
    if os.environ.get("RUNPOD_SSH_KEY") or os.environ.get("RUNPOD_SSH_PRIVATE_KEY", "").strip():
        import fleet
        return Path(fleet.ssh_key_path())
    if not KEY.exists():
        KEY.parent.mkdir(mode=0o700, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(KEY)], check=True)
    return KEY


def public_keys():
    out = api("POST", GRAPHQL, {"query": "query { myself { pubKey } }"})
    keys = (out["data"]["myself"].get("pubKey") or "").splitlines()
    mine = subprocess.run(["ssh-keygen", "-y", "-f", str(key_path())], capture_output=True,
                          text=True, check=True)
    keys.append(mine.stdout.strip())
    seen, kept = set(), []
    for key in (k.strip() for k in keys if k.strip()):
        body = " ".join(key.split()[:2])
        if body not in seen:
            seen.add(body)
            kept.append(key)
    return "\n".join(kept)


def pod_body(args, keys, extra_env=None):
    """The REST request that creates pod `args.name`; `extra_env` adds to its
    environment (POD_BOOT_B64 starts a script at every container start)."""
    body = {
        "name": args.name, "cloudType": args.cloud, "containerDiskInGb": args.disk,
        "volumeInGb": 0, "ports": ["22/tcp"], "dockerEntrypoint": ["bash", "-c"],
        "dockerStartCmd": [STAGE0],
        "env": {"PUBLIC_KEY": keys, "POD_MAX_SECONDS": str(int(args.max_hours * 3600)),
                **(extra_env or {})},
    }
    if args.cpu:
        body.update(computeType="CPU", imageName=args.image or CPU_IMAGE,
                    cpuFlavorIds=args.cpu_flavor or ["cpu5c", "cpu3c"],
                    cpuFlavorPriority="custom", vcpuCount=args.cpu)
    else:
        body.update(computeType="GPU", imageName=args.image or GPU_IMAGE,
                    gpuTypeIds=args.gpu or DEFAULT_GPUS, gpuTypePriority="custom",
                    gpuCount=args.gpu_count, minVCPUPerGPU=args.min_vcpu,
                    minRAMPerGPU=args.min_ram, allowedCudaVersions=["13.0", "12.9", "12.8"])
    return body


def ssh_args(pod):
    port = (pod.get("portMappings") or {}).get("22")
    if not pod.get("publicIp") or not port:
        sys.exit(f"{pod['name']}: no public ssh port yet")
    # Host keys are regenerated at every container start, so they cannot be pinned.
    return ["ssh", "-i", str(key_path()), "-p", str(port), "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
            "-o", "ServerAliveInterval=30", f"root@{pod['publicIp']}"]


def create(args, extra_env=None):
    """Create pod `args.name` and wait until it answers on ssh."""
    if find(args.name):
        sys.exit(f"a pod named {args.name} exists; `down` it first")
    pod = api("POST", f"{REST}/pods", pod_body(args, public_keys(), extra_env))
    print(f"created {pod['id']} ({pod.get('costPerHr')} $/hr); waiting for ssh", flush=True)
    deadline = time.time() + args.wait
    while time.time() < deadline:
        pod = api("GET", f"{REST}/pods/{pod['id']}")
        if pod.get("publicIp") and (pod.get("portMappings") or {}).get("22"):
            probe = subprocess.run([*ssh_args(pod), "-o", "ConnectTimeout=10", "true"],
                                   capture_output=True, check=False)
            if probe.returncode == 0:
                print(json.dumps({k: pod.get(k) for k in ("id", "name", "publicIp", "portMappings",
                                  "vcpuCount", "memoryInGb", "costPerHr", "imageName")}), flush=True)
                return pod
        time.sleep(10)
    sys.exit(f"{pod['id']}: ssh not up after {args.wait} s; the pod is kept (`down` removes it)")


def sync(pod, dest=REMOTE):
    import tree
    data, summary = tree.pack(REPO)
    print(f"shipping {summary['files']} files, {summary['bytes'] / 1e6:.1f} MB to {dest}", flush=True)
    script = f"mkdir -p {dest} && tar --no-same-owner -xzf - -C {dest}"
    return subprocess.run([*ssh_args(pod), script], input=data, check=False).returncode


def fetch(pod, remote, local):
    Path(local).mkdir(parents=True, exist_ok=True)
    parent, leaf = os.path.split(remote.rstrip("/"))
    pack = subprocess.Popen(
        [*ssh_args(pod), f"tar -czf - -C {shlex.quote(parent or '/')} {shlex.quote(leaf)}"],
        stdout=subprocess.PIPE)
    unpack = subprocess.run(["tar", "-xzf", "-", "-C", str(local)], stdin=pack.stdout,
                            check=False)
    pack.wait()
    return pack.returncode or unpack.returncode


def cmd_up(args):
    create(args)
    return 0


def cmd_run(args):
    command = " ".join(args.command)
    if not command:
        sys.exit("run needs a command after --")
    pod = find(args.name)
    created = pod is None
    if created:
        pod = create(args)
    try:
        if sync(pod) != 0:
            return 1
        script = f"{BOOTSTRAP}\n{command}"
        rc = subprocess.run([*ssh_args(pod), f"bash -c {shlex.quote(script)}"],
                            check=False).returncode
        for path in args.out:
            remote = f"{REMOTE}/{path}"
            local = REPO / Path(path).parent
            if fetch(pod, remote, local) != 0:
                print(f"could not fetch {path}", file=sys.stderr)
                rc = rc or 1
        return rc
    finally:
        if created and not args.keep:
            api("DELETE", f"{REST}/pods/{pod['id']}")
            print(f"deleted {pod['id']} ({args.name})", flush=True)


def cmd_ssh(args):
    command = " ".join(args.command) if args.command else None
    return subprocess.run([*ssh_args(need(args.name)), *([command] if command else [])],
                          check=False).returncode


def cmd_sync(args):
    return sync(need(args.name), args.dest or REMOTE)


def cmd_fetch(args):
    return fetch(need(args.name), args.remote, args.local)


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


def add_pod_options(p):
    p.add_argument("--gpu", action="append", default=[], metavar="GPU_TYPE_ID",
                   help="acceptable GPU types, in order of preference (default DEFAULT_GPUS)")
    p.add_argument("--gpu-count", type=int, default=1)
    p.add_argument("--min-vcpu", type=int, default=16, help="vCPUs per GPU")
    p.add_argument("--min-ram", type=int, default=32, help="GB per GPU")
    p.add_argument("--cpu", type=int, default=0, help="a CPU pod with this many vCPUs")
    p.add_argument("--cpu-flavor", action="append", default=[])
    p.add_argument("--cloud", default="SECURE", choices=["SECURE", "COMMUNITY"])
    p.add_argument("--image")
    p.add_argument("--disk", type=int, default=60)
    p.add_argument("--max-hours", type=float, default=6.0)
    p.add_argument("--wait", type=int, default=900)


def parse(argv=None):
    """Arguments; for `run` and `ssh`, whatever follows `--` is the command."""
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run one command on a GPU pod")
    run.add_argument("name")
    add_pod_options(run)
    run.add_argument("--out", action="append", default=[], metavar="PATH",
                     help="a path relative to the repository to copy back")
    run.add_argument("--keep", action="store_true", help="keep the pod afterwards")
    up = sub.add_parser("up")
    up.add_argument("name")
    add_pod_options(up)
    ssh = sub.add_parser("ssh")
    ssh.add_argument("name")
    ssh.add_argument("words", nargs="*", help="the command, if not after --")
    sync_p = sub.add_parser("sync")
    sync_p.add_argument("name")
    sync_p.add_argument("--dest")
    fetch_p = sub.add_parser("fetch")
    fetch_p.add_argument("name")
    fetch_p.add_argument("remote")
    fetch_p.add_argument("local")
    down = sub.add_parser("down")
    down.add_argument("name")
    sub.add_parser("list")
    args = ap.parse_args(argv)
    if args.cmd in ("run", "up") and args.cpu and args.gpu:
        ap.error("--cpu and --gpu are exclusive")
    args.command = getattr(args, "words", []) + command
    return args


def main(argv=None):
    args = parse(argv)
    return {"run": cmd_run, "up": cmd_up, "ssh": cmd_ssh, "sync": cmd_sync, "fetch": cmd_fetch,
            "down": cmd_down, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
