#!/usr/bin/env python3
"""Rent an EC2 instance for experiments, reachable over ssh from your address only.

    deploy/aws/launch.py launch --region us-east-1 --allow-cidr 203.0.113.7/32
    deploy/aws/launch.py run exp --out results/run.json -- 'make && ./build/ca ...'
    deploy/aws/launch.py terminate exp

`launch` starts instance NAME (default `exp`) on Ubuntu 24.04, or the NVIDIA
deep-learning base image for GPU types, and prints the ssh command.  The
pieces are commands too:

    deploy/aws/launch.py launch [--name NAME] [--type T] [--spot] [--hours H] ...
    deploy/aws/launch.py sync NAME
    deploy/aws/launch.py ssh NAME -- 'nproc'
    deploy/aws/launch.py fetch NAME REMOTE_PATH LOCAL_DIR
    deploy/aws/launch.py terminate NAME
    deploy/aws/launch.py list

`sync` and `run` make /home/ubuntu/cryptanalysis this checkout, edits
included, with cloud/ship.py and cloud/install_tree.py, as cloud/runpod_pod.py
does on a pod; `run` copies the --out paths back and exits with CMD's status.

The security group `ca-experiments` admits ssh (22) from the --allow-cidr
ranges and nothing else.  The key is ~/.ssh/id_ed25519 (created if missing,
or --key), imported once as an EC2 key pair named after its fingerprint.
Every instance runs `shutdown -h` after --hours (default 6), and shutdown
terminates it, so a forgotten instance stops billing.  Instances are found by
their Name tag among those tagged ca:experiments.  Needs boto3 and AWS
credentials; the region is --region, else AWS_REGION, else us-east-1.
"""

import argparse
import datetime
import hashlib
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "cloud"))
import ship  # noqa: E402

KEY = Path.home() / ".ssh" / "id_ed25519"
USER = "ubuntu"
REMOTE = f"/home/{USER}/cryptanalysis"
GROUP = "ca-experiments"
TAG = "ca:experiments"
CPU_TYPE = "c7i.4xlarge"
GPU_TYPE = "g7e.2xlarge"
GPU_FAMILIES = ("g", "p")
AMIS = {
    "cpu": "/aws/service/canonical/ubuntu/server/24.04/stable/current/{arch}/hvm/ebs-gp3/ami-id",
    "gpu": "/aws/service/deeplearning/ami/x86_64/"
           "base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id",
}
LIVE = ["pending", "running", "stopping", "stopped"]

# User data, as root at first boot: the lifetime cap first, so that nothing
# later can leave the instance running past it; then the toolchain the
# suite's builds need.  Rust goes to the ssh user, as cloud/pod_env.sh expects.
USER_DATA = r"""#!/bin/bash
shutdown -h +{minutes}
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q build-essential cmake git python3-pip pkg-config libssl-dev curl
sudo -u {user} -H bash -c 'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs |
  sh -s -- -y -q --profile minimal --default-toolchain stable'
touch /var/lib/ca-boot-done
"""

# Before CMD, in the synced checkout: wait for user data, then the toolchain.
# NVRTC (cloud/pod_env.sh) only where there is a GPU to compile for.
BOOTSTRAP = r"""
set -e
while [ ! -e /var/lib/ca-boot-done ]; do sleep 5; done
cd ~/cryptanalysis
export LC_ALL=C.UTF-8 PATH="$HOME/.cargo/bin:$PATH"
if command -v nvidia-smi >/dev/null; then
  source cloud/pod_env.sh
  nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | sed 's/^/gpu: /'
fi
echo "host: $(nproc) vCPU, $(free -g | awk '/^Mem/ {print $2}') GB"
""".strip()


def region(args):
    return args.region or os.environ.get("AWS_REGION") or "us-east-1"


def client(args, service):
    try:
        import boto3
    except ImportError:
        sys.exit("boto3 is not installed: pip install boto3")
    return boto3.client(service, region_name=region(args))


def key_path(args):
    path = Path(args.key).expanduser() if getattr(args, "key", None) else KEY
    if not path.exists():
        if getattr(args, "key", None):
            sys.exit(f"{path}: no such key")
        path.parent.mkdir(mode=0o700, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                       check=True)
    return path


def public_key(path):
    return subprocess.run(["ssh-keygen", "-y", "-f", str(path)], capture_output=True,
                          text=True, check=True).stdout.strip()


def key_pair_name(public):
    """A name fixed by the key, so each machine's key is imported once."""
    return "ca-experiments-" + hashlib.sha256(public.split()[1].encode()).hexdigest()[:12]


def ensure_key_pair(ec2, public):
    name = key_pair_name(public)
    if not ec2.describe_key_pairs(Filters=[{"Name": "key-name", "Values": [name]}])["KeyPairs"]:
        ec2.import_key_pair(KeyName=name, PublicKeyMaterial=public.encode())
    return name


def ensure_group(ec2, cidrs):
    """The `ca-experiments` group in the default VPC, admitting ssh from `cidrs`."""
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        sys.exit("this region has no default VPC")
    vpc = vpcs[0]["VpcId"]
    found = ec2.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [GROUP]}, {"Name": "vpc-id", "Values": [vpc]}])
    if found["SecurityGroups"]:
        group = found["SecurityGroups"][0]
    else:
        gid = ec2.create_security_group(
            GroupName=GROUP, VpcId=vpc, Description="ssh to experiment instances",
            TagSpecifications=[{"ResourceType": "security-group",
                                "Tags": [{"Key": TAG, "Value": "1"}]}])["GroupId"]
        group = {"GroupId": gid, "IpPermissions": []}
    have = {r["CidrIp"] for p in group["IpPermissions"]
            if p.get("FromPort") == 22 and p.get("ToPort") == 22 for r in p.get("IpRanges", [])}
    new = [c for c in cidrs if c not in have]
    if new:
        ec2.authorize_security_group_ingress(GroupId=group["GroupId"], IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": c, "Description": "deploy/aws/launch.py"} for c in new]}])
    return group["GroupId"]


def is_gpu(instance_type):
    return instance_type.split(".")[0].rstrip("0123456789").startswith(GPU_FAMILIES)


def image(ec2, ssm, instance_type):
    """(AMI id, root device name, its snapshot's GB) for `instance_type`."""
    info = ec2.describe_instance_types(InstanceTypes=[instance_type])["InstanceTypes"][0]
    arches = info["ProcessorInfo"]["SupportedArchitectures"]
    if is_gpu(instance_type):
        if "x86_64" not in arches:
            sys.exit(f"{instance_type}: the GPU image is x86_64 only")
        name = AMIS["gpu"]
    else:
        name = AMIS["cpu"].format(arch="amd64" if "x86_64" in arches else "arm64")
    ami = ssm.get_parameter(Name=name)["Parameter"]["Value"]
    found = ec2.describe_images(ImageIds=[ami])["Images"][0]
    root = found["RootDeviceName"]
    size = next((m["Ebs"].get("VolumeSize", 0) for m in found["BlockDeviceMappings"]
                 if m.get("DeviceName") == root and "Ebs" in m), 0)
    return ami, root, size


def run_request(args, ami, key_name, group_id, root="/dev/sda1", min_disk=0, now=None):
    """The run_instances arguments for `args`; no service is called."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    deadline = now + datetime.timedelta(hours=args.hours)
    tags = [{"Key": "Name", "Value": args.name}, {"Key": TAG, "Value": "1"},
            {"Key": "ca:deadline", "Value": deadline.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    request = {
        "ImageId": ami, "InstanceType": args.type, "MinCount": 1, "MaxCount": 1,
        "KeyName": key_name, "SecurityGroupIds": [group_id],
        "UserData": USER_DATA.format(minutes=max(1, round(args.hours * 60)), user=USER),
        "InstanceInitiatedShutdownBehavior": "terminate",
        "MetadataOptions": {"HttpTokens": "required", "HttpEndpoint": "enabled"},
        "BlockDeviceMappings": [{"DeviceName": root, "Ebs": {
            "VolumeSize": max(args.disk, min_disk), "VolumeType": "gp3", "Encrypted": True,
            "DeleteOnTermination": True}}],
        "TagSpecifications": [{"ResourceType": "instance", "Tags": tags},
                              {"ResourceType": "volume", "Tags": tags}],
    }
    if args.spot:
        request["InstanceMarketOptions"] = {"MarketType": "spot", "SpotOptions": {
            "SpotInstanceType": "one-time", "InstanceInterruptionBehavior": "terminate"}}
    return request


def instances(ec2, name=None):
    filters = [{"Name": f"tag:{TAG}", "Values": ["1"]},
               {"Name": "instance-state-name", "Values": LIVE}]
    if name:
        filters.append({"Name": "tag:Name", "Values": [name]})
    out = ec2.describe_instances(Filters=filters)
    return [i for r in out["Reservations"] for i in r["Instances"]]


def tag(instance, key):
    return next((t["Value"] for t in instance.get("Tags", []) if t["Key"] == key), None)


def need(ec2, name):
    found = instances(ec2, name)
    if not found:
        sys.exit(f"no experiment instance named {name}")
    return found[0]


def ssh_args(args, instance):
    host = instance.get("PublicIpAddress")
    if not host:
        sys.exit(f"{instance['InstanceId']}: no public address yet")
    return ["ssh", "-i", str(key_path(args)), "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30",
            f"{USER}@{host}"]


def cmd_launch(args):
    ec2, ssm = client(args, "ec2"), client(args, "ssm")
    if instances(ec2, args.name):
        sys.exit(f"an instance named {args.name} is already up (`terminate {args.name}` first)")
    key_name = ensure_key_pair(ec2, public_key(key_path(args)))
    group_id = ensure_group(ec2, args.allow_cidr)
    ami, root, min_disk = image(ec2, ssm, args.type)
    request = run_request(args, ami, key_name, group_id, root, min_disk)
    instance = ec2.run_instances(**request)["Instances"][0]
    iid = instance["InstanceId"]
    print(f"launched {iid} ({args.type}{', spot' if args.spot else ''}) as {args.name} "
          f"in {region(args)}; terminates itself after {args.hours:g} h", flush=True)
    ec2.get_waiter("instance_running").wait(InstanceIds=[iid])
    instance = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
    command = " ".join(map(shlex.quote, ssh_args(args, instance)))
    print(f"running at {instance.get('PublicIpAddress')}\n  {command}", flush=True)
    if args.wait:
        deadline = time.time() + args.wait
        while time.time() < deadline:
            probe = subprocess.run([*ssh_args(args, instance), "-o", "ConnectTimeout=10",
                                    "test -e /var/lib/ca-boot-done"],
                                   capture_output=True, check=False)
            if probe.returncode == 0:
                print("toolchain installed; ready", flush=True)
                return 0
            time.sleep(10)
        print(f"not ready after {args.wait} s; the instance is kept", file=sys.stderr)
        return 1
    return 0


def sync(args, instance):
    staged = f"{REMOTE}.tree"
    # ship.py's cache defaults to /root, which the ssh user cannot write.
    prefix = [*ssh_args(args, instance), f"SHIP_CACHE=/home/{USER}/.cache/checkout.git"]
    summary = ship.ship(prefix, REPO, staged, log=lambda m: print(m, flush=True))
    if summary["returncode"] != 0:
        return summary["returncode"]
    install = f"python3 {staged}/cloud/install_tree.py {staged} {REMOTE}"
    return subprocess.run([*ssh_args(args, instance), install], check=False).returncode


def fetch(args, instance, remote, local):
    Path(local).mkdir(parents=True, exist_ok=True)
    parent, leaf = os.path.split(remote.rstrip("/"))
    pack = subprocess.Popen(
        [*ssh_args(args, instance),
         f"tar -czf - -C {shlex.quote(parent or '/')} {shlex.quote(leaf)}"],
        stdout=subprocess.PIPE)
    unpack = subprocess.run(["tar", "-xzf", "-", "-C", str(local)], stdin=pack.stdout,
                            check=False)
    pack.wait()
    return pack.returncode or unpack.returncode


def cmd_run(args):
    command = " ".join(args.command)
    if not command:
        sys.exit("run needs a command after --")
    instance = need(client(args, "ec2"), args.name)
    if sync(args, instance) != 0:
        return 1
    script = f"{BOOTSTRAP}\n{command}"
    rc = subprocess.run([*ssh_args(args, instance), f"bash -c {shlex.quote(script)}"],
                        check=False).returncode
    for path in args.out:
        if fetch(args, instance, f"{REMOTE}/{path}", REPO / Path(path).parent) != 0:
            print(f"could not fetch {path}", file=sys.stderr)
            rc = rc or 1
    return rc


def cmd_sync(args):
    return sync(args, need(client(args, "ec2"), args.name))


def cmd_ssh(args):
    command = " ".join(args.command) if args.command else None
    instance = need(client(args, "ec2"), args.name)
    return subprocess.run([*ssh_args(args, instance), *([command] if command else [])],
                          check=False).returncode


def cmd_fetch(args):
    return fetch(args, need(client(args, "ec2"), args.name), args.remote, args.local)


def cmd_terminate(args):
    ec2 = client(args, "ec2")
    instance = need(ec2, args.name)
    ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    print(f"terminated {instance['InstanceId']} ({args.name})")
    return 0


def cmd_list(args):
    for i in instances(client(args, "ec2")):
        spot = " spot" if i.get("InstanceLifecycle") == "spot" else ""
        print(f"{i['InstanceId']}  {tag(i, 'Name')}  {i['State']['Name']}  "
              f"{i['InstanceType']}{spot}  {i.get('PublicIpAddress', '-')}  "
              f"until {tag(i, 'ca:deadline')}")
    return 0


def parse(argv=None):
    """Arguments; for `run` and `ssh`, whatever follows `--` is the command."""
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--region", help="default: AWS_REGION, else us-east-1")
    common.add_argument("--key", help=f"private ssh key (default {KEY})")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    launch = sub.add_parser("launch", parents=[common], help="start an experiment instance")
    launch.add_argument("--name", default="exp")
    launch.add_argument("--allow-cidr", action="append", required=True, metavar="CIDR",
                        help="who may ssh in, e.g. your address as A.B.C.D/32 (repeatable)")
    launch.add_argument("--type", help=f"instance type (default {CPU_TYPE}, or {GPU_TYPE} "
                                       "with --gpu)")
    launch.add_argument("--gpu", action="store_true", help=f"shorthand for --type {GPU_TYPE}")
    launch.add_argument("--spot", action="store_true")
    launch.add_argument("--hours", type=float, default=6.0, help="lifetime cap (default 6)")
    launch.add_argument("--disk", type=int, default=100, help="root volume GB (default 100)")
    launch.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="also wait this long for ssh and the toolchain")
    run = sub.add_parser("run", parents=[common], help="sync, run CMD, copy --out back")
    run.add_argument("name")
    run.add_argument("--out", action="append", default=[], metavar="PATH",
                     help="a path relative to the repository to copy back")
    ssh_p = sub.add_parser("ssh", parents=[common])
    ssh_p.add_argument("name")
    ssh_p.add_argument("words", nargs="*", help="the command, if not after --")
    sync_p = sub.add_parser("sync", parents=[common])
    sync_p.add_argument("name")
    fetch_p = sub.add_parser("fetch", parents=[common])
    fetch_p.add_argument("name")
    fetch_p.add_argument("remote")
    fetch_p.add_argument("local")
    term = sub.add_parser("terminate", parents=[common])
    term.add_argument("name")
    sub.add_parser("list", parents=[common])
    args = ap.parse_args(argv)
    if args.cmd == "launch":
        if args.gpu and args.type and not is_gpu(args.type):
            ap.error(f"--gpu with a non-GPU --type {args.type}")
        args.type = args.type or (GPU_TYPE if args.gpu else CPU_TYPE)
        if args.hours <= 0:
            ap.error("--hours must be positive")
        for cidr in args.allow_cidr:
            if "/" not in cidr:
                ap.error(f"--allow-cidr {cidr}: give a range, e.g. {cidr}/32")
            if cidr.endswith("/0"):
                ap.error(f"--allow-cidr {cidr} opens ssh to the whole internet")
    args.command = getattr(args, "words", []) + command
    return args


def main(argv=None):
    args = parse(argv)
    return {"launch": cmd_launch, "run": cmd_run, "ssh": cmd_ssh, "sync": cmd_sync,
            "fetch": cmd_fetch, "terminate": cmd_terminate, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
