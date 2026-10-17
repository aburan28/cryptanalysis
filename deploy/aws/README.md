# EC2 instances for experiments

**This directory makes no performance claim.** It is plumbing: it rents an
EC2 instance, puts this checkout on it, and gives it back. No row in
[`docs/BENCHMARKS.md`](../../docs/BENCHMARKS.md) moves because of it.

`launch.py` is the AWS counterpart of
[`cloud/runpod_pod.py`](../../cloud/runpod_pod.py): one instance, reachable
over ssh from the addresses you name, with this checkout (edits included)
synced to it by [`cloud/ship.py`](../../cloud/ship.py).

```sh
pip install boto3
python3 deploy/aws/launch.py launch --region us-east-1 --allow-cidr YOUR.IP/32
python3 deploy/aws/launch.py run exp --out results/run.json -- \
    'cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j"$(nproc)" && ...'
python3 deploy/aws/launch.py terminate exp
```

`YOUR.IP` is the public address of the machine you ssh from
(`curl -s https://checkip.amazonaws.com`), not of a cloud agent's VM.

## Commands

| command | does |
|---|---|
| `launch [--name exp] --allow-cidr CIDR ... [--type T \| --gpu] [--spot] [--hours 6] [--disk 100] [--wait S]` | start the instance; print its ssh command |
| `run NAME [--out PATH ...] -- CMD` | sync this checkout to `~/cryptanalysis`, wait for the toolchain, run CMD, copy the `--out` paths back; exits with CMD's status |
| `sync NAME` | only the sync |
| `ssh NAME [-- CMD]` | a shell, or one command |
| `fetch NAME REMOTE_PATH LOCAL_DIR` | copy a path back |
| `terminate NAME` | terminate it |
| `list` | the experiment instances in the region, with their deadlines |

Every command takes `--region` (default `AWS_REGION`, else `us-east-1`) and
`--key` (default `~/.ssh/id_ed25519`, created when missing).

## What it creates

* **The instance.** Ubuntu 24.04 on CPU types (x86_64 or Graviton, from the
  type), the NVIDIA deep-learning base image (Ubuntu 24.04) on `g*` and `p*`
  types. The defaults are `c7i.4xlarge` (16 vCPU, 32 GB) and, with `--gpu`,
  `g7e.2xlarge` (RTX PRO 6000 Blackwell, sm_120). It has IMDSv2 only and an
  encrypted gp3 root volume deleted with it. It is tagged `ca:experiments`,
  `Name` and `ca:deadline`. User data installs build-essential, cmake, git,
  pip and Rust stable. `run` waits for that, and on GPU instances it also
  sources [`cloud/pod_env.sh`](../../cloud/pod_env.sh) for NVRTC.
* **The security group `ca-experiments`** in the default VPC. It admits tcp/22
  from the `--allow-cidr` ranges and nothing else. Ranges accumulate: revoke
  old addresses in the console when they change. `0.0.0.0/0` is refused.
* **An EC2 key pair** `ca-experiments-<hash of your public key>`, imported
  once per key.

## Cost guards

* The first line of user data is `shutdown -h +MINUTES` (`--hours`, default
  6), and the instance's shutdown behaviour is *terminate*. A forgotten
  instance therefore terminates itself; `list` shows each deadline.
* `--spot` asks for a one-time spot instance that terminates on interruption.
* `launch` refuses a name that is already up.
* Terminate the instance when the experiment is done. The deadline is a
  backstop, not the plan.

## Checks

```sh
python3 -m unittest discover -s deploy/aws/tests -v
```

The tests build the EC2 requests against a fake client; no AWS account is
needed. CI runs them with shellcheck on the user data
(`.github/workflows/cloud.yml`).

Checked on real AWS (account 104186811093, us-east-1, 2026-10-17): `launch
--type t3.small --hours 0.25` imported the key pair, created the security
group, started the instance and printed its ssh command. The console log
showed `Shutdown scheduled` 15 minutes after boot, the shutdown behaviour read
`terminate`, and `terminate` removed it. ssh, `sync` and `run` were not
exercised there: the agent VM that ran the check has no outbound ssh.
