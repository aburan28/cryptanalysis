#!/usr/bin/env python3
"""Manage the Runpod pods that host this repository's Cursor workers.

Every pod named in cloud/fleet.json boots cloud/worker/boot.sh, which keeps a
toolchain for this repository under /workspace and registers a Cursor
self-hosted ("My Machines") worker under the pod's name.  Agents started on
that worker run on the pod's cores and GPU.

  status                        pods, cost, Cursor registration, account balance
  up NAME... [--wait]           create or start pods; --update re-applies fleet.json
  stop NAME...                  stop pods (the /workspace volume is kept)
  down NAME... --yes            terminate pods (the /workspace volume is deleted)
  ssh NAME [CMD...]             a shell, or one command, on the pod
  logs NAME [--file F] [-f]     boot/worker/toolchain/idle logs; --state for status files
  run NAME [opts] -- CMD...     run CMD on a copy of this checkout and fetch the results
  jobs NAME                     list `run` jobs on the pod
  job NAME ID --logs|--fetch|--kill
  rekey NAME...                 push the current CURSOR_API_KEY (and GITHUB_TOKEN) to pods
  agent NAME PROMPT [--wait]    start a Cursor cloud agent on the pod's worker

Credentials come from the environment: RUNPOD_API_KEY for everything;
CURSOR_API_KEY for up, rekey, agent and the worker column of status;
GITHUB_TOKEN (optional) so agents on the pods can push; and, for ssh, logs,
run and jobs, an SSH key: RUNPOD_SSH_KEY (a path), RUNPOD_SSH_PRIVATE_KEY (the
key itself), or ~/.ssh/id_ed25519.
"""
import argparse
import base64
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
sys.path.insert(0, str(HERE))
import tree  # noqa: E402

FLEET_FILE = HERE / "fleet.json"
REST = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
CURSOR = "https://api.cursor.com"
LOG_FILES = ("boot", "worker", "toolchain", "idle", "msolve-build", "sage-install", "cuda13-fetch")
TERMINAL_RUN_STATES = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}

# The pod's start command.  It refreshes the fleet source (this directory, at
# fleet.json's fleetRef, else fallbackRef), runs cloud/worker/boot.sh in the
# background, and hands PID 1 to the image's own /start.sh, which starts sshd
# with the PUBLIC_KEY variable.
STAGE0 = r"""
F=/workspace/fleet
mkdir -p "$F/logs"
command -v git >/dev/null 2>&1 || { apt-get update -qq; apt-get install -y -qq git ca-certificates; }
fetch() {
  if [ -d "$F/src/.git" ]; then
    git -C "$F/src" fetch -q --depth 1 origin "$1" && git -C "$F/src" checkout -q -f FETCH_HEAD
  else
    rm -rf "$F/src" && git clone -q --depth 1 --branch "$1" "$FLEET_REPO" "$F/src"
  fi
}
for ref in "$FLEET_REF" "$FLEET_FALLBACK_REF"; do
  for _ in 1 2 3 4 5; do
    fetch "$ref" && break 2
    sleep 10
  done
done
if [ -f "$F/src/cloud/worker/boot.sh" ]; then
  (bash "$F/src/cloud/worker/boot.sh" 2>&1 | tee -a "$F/logs/boot.log") &
else
  echo "fleet: no cloud/worker/boot.sh at $FLEET_REF or $FLEET_FALLBACK_REF"
fi
[ -x /start.sh ] && exec /start.sh
exec sleep infinity
""".strip()


class ApiError(RuntimeError):
    pass


def need(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set (add it to Cursor Dashboard > Cloud Agents > Secrets)")
    return value


def http(method, url, headers, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        **headers, "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "cryptanalysis-fleet/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:600]
        raise ApiError(f"{method} {url}: HTTP {err.code}: {detail}") from None
    except urllib.error.URLError as err:
        raise ApiError(f"{method} {url}: {err.reason}") from None
    return json.loads(raw) if raw.strip() else None


def runpod(method, path, body=None):
    return http(method, REST + path, {"Authorization": f"Bearer {need('RUNPOD_API_KEY')}"}, body)


def graphql(query):
    out = http("POST", GRAPHQL, {"Authorization": f"Bearer {need('RUNPOD_API_KEY')}"},
               {"query": query})
    if out.get("errors"):
        raise ApiError(f"graphql: {out['errors']}")
    return out["data"]


def cursor(method, path, body=None):
    token = base64.b64encode(f"{need('CURSOR_API_KEY')}:".encode()).decode()
    return http(method, CURSOR + path, {"Authorization": f"Basic {token}"}, body)


# ---- fleet.json and pods --------------------------------------------------------

def load_fleet(path=FLEET_FILE):
    return json.loads(Path(path).read_text())


def spec_for(fleet, name):
    try:
        return fleet["workers"][name]
    except KeyError:
        sys.exit(f"unknown worker {name!r}; cloud/fleet.json defines {', '.join(fleet['workers'])}")


def pod_env(name, spec, fleet, *, cursor_key, github_token=None, public_keys="", ref=None):
    labels = {"kind": spec["computeType"].lower(), **spec.get("labels", {})}
    env = {
        "FLEET_WORKER_NAME": name,
        "FLEET_REPO": fleet["repo"],
        "FLEET_REF": ref or fleet["fleetRef"],
        "FLEET_FALLBACK_REF": fleet["fallbackRef"],
        "FLEET_WORKER_BRANCH": fleet["workerBranch"],
        "FLEET_FEATURES": ",".join(spec.get("features", [])),
        "FLEET_LABELS": ",".join(f"{k}={v}" for k, v in sorted(labels.items())),
        "FLEET_IDLE_STOP_MINUTES": str(spec.get("idleStopMinutes", 0)),
        "CURSOR_API_KEY": cursor_key,
    }
    if github_token:
        env["GITHUB_TOKEN"] = github_token
    if public_keys:
        env["PUBLIC_KEY"] = public_keys
    return env


def pod_body(name, spec, fleet, env):
    body = {
        "name": name,
        "computeType": spec["computeType"],
        "imageName": spec["imageName"],
        "cloudType": spec.get("cloudType", "SECURE"),
        "containerDiskInGb": spec["containerDiskInGb"],
        "volumeInGb": spec["volumeInGb"],
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "dockerEntrypoint": ["bash", "-c"],
        "dockerStartCmd": [STAGE0],
        "env": env,
    }
    if spec["computeType"] == "CPU":
        body.update(cpuFlavorIds=spec["cpuFlavorIds"], cpuFlavorPriority="custom",
                    vcpuCount=spec["vcpuCount"])
    else:
        body.update(gpuTypeIds=spec["gpuTypeIds"], gpuTypePriority="custom",
                    gpuCount=spec.get("gpuCount", 1))
        for key in ("minVCPUPerGPU", "minRAMPerGPU", "allowedCudaVersions"):
            if key in spec:
                body[key] = spec[key]
    for key in ("dataCenterIds", "countryCodes", "interruptible"):
        if key in spec:
            body[key] = spec[key]
    return body


def list_pods():
    pods = runpod("GET", "/pods")
    return pods if isinstance(pods, list) else pods.get("pods", [])


def find_pod(name, pods):
    live = [p for p in pods if p.get("name") == name and p.get("desiredStatus") != "TERMINATED"]
    live.sort(key=lambda p: (p.get("desiredStatus") != "RUNNING", p.get("lastStartedAt") or ""))
    return live[0] if live else None


def pod_or_exit(name, pods=None):
    pod = find_pod(name, list_pods() if pods is None else pods)
    if pod is None:
        sys.exit(f"{name}: no pod (create it with `cloud/fleet.py up {name}`)")
    return pod


def public_keys():
    """The account's registered SSH keys plus the local one, as PUBLIC_KEY wants them."""
    keys = (graphql("query { myself { pubKey } }")["myself"].get("pubKey") or "").splitlines()
    local = ssh_key_path(required=False)
    if local and Path(f"{local}.pub").exists():
        keys.append(Path(f"{local}.pub").read_text().strip())
    seen, out = set(), []
    for key in (k.strip() for k in keys):
        body = " ".join(key.split()[:2])
        if key and body not in seen:
            seen.add(body)
            out.append(key)
    return "\n".join(out)


def cursor_workers():
    if not os.environ.get("CURSOR_API_KEY"):
        return None
    return cursor("GET", "/v0/private-workers?scope=personal&limit=100").get("workers", [])


# ---- ssh ------------------------------------------------------------------------------

def openssh_private_key(text):
    """OpenSSH cannot load a PKCS#8 ("BEGIN PRIVATE KEY") Ed25519 key; convert it."""
    text = text.strip() + "\n"
    if "BEGIN PRIVATE KEY" not in text:
        return text
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        sys.exit("RUNPOD_SSH_PRIVATE_KEY is PKCS#8; install `cryptography` or store it in "
                 "OpenSSH format (ssh-keygen writes that by default)")
    key = serialization.load_pem_private_key(text.encode(), password=None)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                             serialization.NoEncryption()).decode()


def ssh_key_path(required=True):
    if os.environ.get("RUNPOD_SSH_KEY"):
        return os.path.expanduser(os.environ["RUNPOD_SSH_KEY"])
    material = os.environ.get("RUNPOD_SSH_PRIVATE_KEY", "").strip()
    if material:
        path = Path.home() / ".cache" / "cryptanalysis-fleet" / "ssh_key"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        text = openssh_private_key(material.replace("\\n", "\n"))
        if not path.exists() or path.read_text() != text:
            path.touch(mode=0o600)
            path.write_text(text)
        return str(path)
    default = Path.home() / ".ssh" / "id_ed25519"
    if default.exists():
        return str(default)
    if required:
        sys.exit("no SSH key: set RUNPOD_SSH_KEY or RUNPOD_SSH_PRIVATE_KEY")
    return None


def ssh_endpoint(pod):
    port = (pod.get("portMappings") or {}).get("22")
    return (pod.get("publicIp"), int(port)) if pod.get("publicIp") and port else None


def ssh_base(pod):
    endpoint = ssh_endpoint(pod)
    if endpoint is None:
        sys.exit(f"{pod['name']}: no public SSH port yet (status {pod.get('desiredStatus')})")
    host, port = endpoint
    # Host keys are regenerated at every container start, so they cannot be pinned.
    return ["ssh", "-i", ssh_key_path(), "-p", str(port), "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
            "-o", "ServerAliveInterval=30", f"root@{host}"]


def remote(pod, script, **kwargs):
    """Run a bash script on the pod with the fleet environment loaded."""
    wrapped = "source /workspace/fleet/env.sh 2>/dev/null; " + script
    return subprocess.run(ssh_base(pod) + [f"bash -c {shlex.quote(wrapped)}"], **kwargs)


# ---- commands ------------------------------------------------------------------------------

def cmd_status(args):
    fleet = load_fleet()
    pods = list_pods()
    workers = cursor_workers()
    me = graphql("query { myself { clientBalance currentSpendPerHr spendLimit } }")["myself"]
    rows = []
    for name, spec in fleet["workers"].items():
        pod = find_pod(name, pods)
        row = {"name": name, "pod": None, "status": "absent", "cost_per_hr": None,
               "hardware": spec.get("description", ""), "ssh": None, "cursor": None}
        if pod:
            gpu = pod.get("gpu") or {}
            hardware = f"{pod.get('vcpuCount')} vCPU, {pod.get('memoryInGb')} GB"
            if gpu.get("displayName"):
                hardware += f", {gpu.get('count', 1)}x {gpu['displayName']}"
            row.update(pod=pod["id"], status=pod.get("desiredStatus"),
                       cost_per_hr=pod.get("costPerHr"), hardware=hardware,
                       ssh=":".join(map(str, ssh_endpoint(pod) or ())) or None)
        if workers is not None:
            match = [w for w in workers if w.get("name") == name]
            row["cursor"] = ("in use" if match[0].get("isInUse") else "connected") if match else "offline"
        rows.append(row)
    if args.json:
        print(json.dumps({"account": me, "workers": rows}, indent=1))
        return 0
    print(f"{'worker':10} {'status':8} {'$/hr':>6}  {'cursor':10} {'ssh':22} hardware")
    for r in rows:
        cost = f"{r['cost_per_hr']:.2f}" if r["cost_per_hr"] is not None else "-"
        print(f"{r['name']:10} {r['status'] or '-':8} {cost:>6}  {r['cursor'] or '?':10} "
              f"{r['ssh'] or '-':22} {r['hardware']}")
    spend = me.get("currentSpendPerHr") or 0
    runway = f", about {me['clientBalance'] / spend:.0f} h at this rate" if spend else ""
    print(f"\nRunpod balance ${me.get('clientBalance', 0):.2f}; account spend "
          f"${spend:.2f}/hr across all pods{runway}.")
    if workers is None:
        print("(set CURSOR_API_KEY to see whether each Cursor worker is connected)")
    return 0


def wait_for_workers(names, timeout):
    deadline = time.time() + timeout
    pending = list(names)
    while pending:
        connected = {w.get("name") for w in cursor_workers() or []}
        for name in [n for n in pending if n in connected]:
            print(f"{name}: Cursor worker connected")
            pending.remove(name)
        if not pending:
            return 0
        if time.time() > deadline:
            print(f"timed out waiting for {', '.join(pending)}; see `cloud/fleet.py logs NAME`")
            return 1
        time.sleep(20)
    return 0


def cmd_up(args):
    fleet = load_fleet()
    key = need("CURSOR_API_KEY")
    github = os.environ.get("GITHUB_TOKEN") or None
    pods = list_pods()
    keys = public_keys()
    for name in args.names:
        spec = spec_for(fleet, name)
        env = pod_env(name, spec, fleet, cursor_key=key, github_token=github,
                      public_keys=keys, ref=args.ref)
        pod = find_pod(name, pods)
        if pod and args.recreate:
            runpod("DELETE", f"/pods/{pod['id']}")
            print(f"{name}: terminated pod {pod['id']} to recreate it")
            pod = None
        if pod is None:
            created = runpod("POST", "/pods", pod_body(name, spec, fleet, env))
            print(f"{name}: created pod {created['id']} (${created.get('costPerHr')}/hr)")
        elif args.update:
            runpod("PATCH", f"/pods/{pod['id']}", {"env": env, "dockerStartCmd": [STAGE0],
                                                    "dockerEntrypoint": ["bash", "-c"]})
            print(f"{name}: updated pod {pod['id']}; it resets and boots again")
        elif pod.get("desiredStatus") == "RUNNING":
            print(f"{name}: pod {pod['id']} already running")
        else:
            try:
                runpod("POST", f"/pods/{pod['id']}/start")
                print(f"{name}: starting pod {pod['id']}")
            except ApiError as err:
                sys.exit(f"{name}: could not start pod {pod['id']} ({err}).\n"
                         f"Its machine may have no free GPU; `up --recreate {name}` rents a "
                         f"new one (the old /workspace volume is lost).")
    return wait_for_workers(args.names, args.timeout) if args.wait else 0


def cmd_stop(args):
    pods = list_pods()
    for name in args.names:
        pod = pod_or_exit(name, pods)
        runpod("POST", f"/pods/{pod['id']}/stop")
        print(f"{name}: stopping pod {pod['id']} (volume kept; `up {name}` restarts it)")
    return 0


def cmd_down(args):
    if not args.yes:
        sys.exit("down terminates the pods and deletes their /workspace volumes; pass --yes")
    pods = list_pods()
    for name in args.names:
        pod = pod_or_exit(name, pods)
        runpod("DELETE", f"/pods/{pod['id']}")
        print(f"{name}: terminated pod {pod['id']}")
    return 0


def cmd_ssh(args):
    pod = pod_or_exit(args.name)
    if not args.command:
        os.execvp("ssh", ssh_base(pod) + ["-t"])
    return remote(pod, shlex.join(args.command)).returncode


def cmd_logs(args):
    pod = pod_or_exit(args.name)
    if args.state:
        script = ("for f in machine toolchain idle; do echo \"== $f.json\"; "
                  "cat /workspace/fleet/$f.json 2>/dev/null || echo '(none yet)'; done; "
                  "echo '== tmux'; tmux ls 2>/dev/null; echo '== agent'; agent --version")
    else:
        script = (f"tail -n {int(args.lines)} {'-F' if args.follow else ''} "
                  f"/workspace/fleet/logs/{shlex.quote(args.file)}.log")
    return remote(pod, script).returncode


def job_env(job, workdir, command, outs, changed):
    values = {"JOB_ID": job, "JOB_DIR": f"/workspace/jobs/{job}", "JOB_WORKDIR": workdir,
              "JOB_SRC": f"/workspace/jobs/{job}/src.tar.gz", "JOB_CMD": command,
              "JOB_OUTS": "\n".join(outs), "JOB_CHANGED": "1" if changed else "0"}
    return " ".join(f"export {k}={shlex.quote(v)};" for k, v in values.items())


def fetch_outputs(pod, job, dest, tag):
    out = remote(pod, f"f=/workspace/jobs/{job}/out.tar.gz; [ -f $f ] && cat $f",
                 capture_output=True)
    if out.returncode != 0 or not out.stdout:
        print(f"job {job}: no outputs to fetch")
        return []
    written = tree.merge_outputs(out.stdout, dest, tag, {})
    for path in written:
        print(f"  fetched {path}")
    return written


def cmd_run(args):
    command = shlex.join(args.command) if len(args.command) > 1 else args.command[0]
    pod = pod_or_exit(args.name)
    root = tree.repo_root()
    data, summary = tree.pack(root, include=args.include)
    job = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + os.urandom(2).hex()
    jobdir = f"/workspace/jobs/{job}"
    workdir = f"/workspace/scratch/{args.dir}" if args.dir else f"{jobdir}/repo"
    print(f"job {job} on {args.name}: {summary['files']} files, {summary['bytes'] / 1e6:.1f} MB"
          + (f" ({len(summary['skipped'])} large files skipped)" if summary["skipped"] else ""),
          file=sys.stderr)
    upload = remote(pod, f"mkdir -p {jobdir} && cat > {jobdir}/src.tar.gz", input=data)
    runner = remote(pod, f"cat > {jobdir}/runner.sh",
                    input=(HERE / "job_runner.sh").read_bytes())
    if upload.returncode or runner.returncode:
        sys.exit("upload failed")
    env = job_env(job, workdir, command, args.out, args.changed)
    if args.detach:
        script = (f"cd /workspace; setsid nohup bash -c {shlex.quote(env + f' bash {jobdir}/runner.sh')} "
                  f"> {jobdir}/console.txt 2>&1 < /dev/null & echo $! > {jobdir}/pid")
        remote(pod, script, check=True)
        print(f"started {job}; follow with `cloud/fleet.py job {args.name} {job} --logs -f`, "
              f"fetch with `--fetch`")
        return 0
    rc = remote(pod, f"cd /workspace; echo $$ > {jobdir}/pid; {env} bash {jobdir}/runner.sh").returncode
    fetch_outputs(pod, job, root, f"{args.name}-{job}")
    return rc


def cmd_jobs(args):
    pod = pod_or_exit(args.name)
    script = r"""
cd /workspace/jobs 2>/dev/null || exit 0
for j in $(ls -1t | head -n 30); do
  if [ -f "$j/status.json" ]; then s="exit $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["returncode"])' "$j/status.json")"
  elif [ -f "$j/pid" ] && kill -0 "$(cat "$j/pid")" 2>/dev/null; then s=running
  else s=stopped; fi
  printf '%-22s %-9s %s\n' "$j" "$s" "$(sed -n 's/^== \$ //p' "$j/log.txt" 2>/dev/null | head -n1 | cut -c1-90)"
done"""
    return remote(pod, script).returncode


def cmd_job(args):
    pod = pod_or_exit(args.name)
    jobdir = f"/workspace/jobs/{shlex.quote(args.id)}"
    if args.fetch:
        fetch_outputs(pod, args.id, tree.repo_root(), f"{args.name}-{args.id}")
        return 0
    if args.kill:
        return remote(pod, f"kill -TERM -- -$(cat {jobdir}/pid) && echo killed").returncode
    return remote(pod, f"tail -n +1 {'-F' if args.follow else ''} {jobdir}/log.txt").returncode


def cmd_rekey(args):
    fleet = load_fleet()
    key = need("CURSOR_API_KEY")
    github = os.environ.get("GITHUB_TOKEN") or None
    pods = list_pods()
    for name in args.names:
        pod = pod_or_exit(name, pods)
        current = runpod("GET", f"/pods/{pod['id']}").get("env") or {}
        env = {**current, "CURSOR_API_KEY": key}
        if github:
            env["GITHUB_TOKEN"] = github
        spec_for(fleet, name)
        runpod("PATCH", f"/pods/{pod['id']}", {"env": env})
        print(f"{name}: new credentials set; the pod resets and its worker reconnects")
    return 0


def cmd_agent(args):
    fleet = load_fleet()
    spec_for(fleet, args.name)
    body = {"prompt": {"text": args.prompt}, "env": {"type": "machine", "name": args.name},
            "repos": [{"url": fleet["repo"].removesuffix(".git"),
                       "startingRef": args.ref or fleet["workerBranch"]}],
            "autoCreatePR": args.pr}
    if args.model:
        body["model"] = {"id": args.model}
    created = cursor("POST", "/v1/agents", body)
    agent, run = created["agent"], created["run"]
    print(f"agent {agent['id']} on {args.name}: {agent.get('url')}")
    if not args.wait:
        return 0
    while True:
        state = cursor("GET", f"/v1/agents/{agent['id']}/runs/{run['id']}")
        if state.get("status") in TERMINAL_RUN_STATES:
            break
        time.sleep(15)
    print(f"run {state['status']} after {state.get('durationMs', 0) / 1000:.0f} s")
    if state.get("result"):
        print(state["result"])
    return 0 if state["status"] == "FINISHED" else 1


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="pods, cost and Cursor registration")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("up", help="create or start pods")
    s.add_argument("names", nargs="+")
    s.add_argument("--wait", action="store_true", help="wait for the Cursor workers to connect")
    s.add_argument("--timeout", type=int, default=1800)
    s.add_argument("--ref", help="boot the pods from this branch instead of fleet.json's fleetRef")
    s.add_argument("--update", action="store_true",
                   help="re-apply fleet.json's environment to running pods (resets them)")
    s.add_argument("--recreate", action="store_true",
                   help="terminate and rent new pods (their /workspace volumes are lost)")
    s.set_defaults(fn=cmd_up)

    s = sub.add_parser("stop", help="stop pods, keeping their volumes")
    s.add_argument("names", nargs="+")
    s.set_defaults(fn=cmd_stop)

    s = sub.add_parser("down", help="terminate pods and delete their volumes")
    s.add_argument("names", nargs="+")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(fn=cmd_down)

    s = sub.add_parser("ssh", help="a shell or one command on a pod")
    s.add_argument("name")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_ssh)

    s = sub.add_parser("logs", help="tail a fleet log on a pod")
    s.add_argument("name")
    s.add_argument("--file", default="boot", choices=LOG_FILES)
    s.add_argument("-n", "--lines", default=60)
    s.add_argument("-f", "--follow", action="store_true")
    s.add_argument("--state", action="store_true", help="show machine/toolchain/idle status")
    s.set_defaults(fn=cmd_logs)

    s = sub.add_parser("run", help="run a command on a copy of this checkout")
    s.add_argument("name")
    s.add_argument("--out", action="append", default=[], metavar="PATH",
                   help="path (relative to the repo root) to copy back; repeatable")
    s.add_argument("--changed", action="store_true",
                   help="copy back every file the command created or modified")
    s.add_argument("--include", action="append", default=[], metavar="PATH",
                   help="also ship this ignored path; repeatable")
    s.add_argument("--dir", metavar="NAME",
                   help="run in /workspace/scratch/NAME, kept between jobs (warm builds)")
    s.add_argument("--detach", action="store_true", help="return at once; see `job`")
    s.set_defaults(fn=cmd_run, command=[])

    s = sub.add_parser("jobs", help="list `run` jobs on a pod")
    s.add_argument("name")
    s.set_defaults(fn=cmd_jobs)

    s = sub.add_parser("job", help="logs, outputs or kill for one job")
    s.add_argument("name")
    s.add_argument("id")
    group = s.add_mutually_exclusive_group()
    group.add_argument("--logs", action="store_true", help="print the log (default)")
    group.add_argument("--fetch", action="store_true", help="copy the outputs back")
    group.add_argument("--kill", action="store_true")
    s.add_argument("-f", "--follow", action="store_true")
    s.set_defaults(fn=cmd_job)

    s = sub.add_parser("rekey", help="push the current CURSOR_API_KEY/GITHUB_TOKEN to pods")
    s.add_argument("names", nargs="+")
    s.set_defaults(fn=cmd_rekey)

    s = sub.add_parser("agent", help="start a Cursor cloud agent on a pod's worker")
    s.add_argument("name")
    s.add_argument("prompt")
    s.add_argument("--ref", help="starting branch (default: fleet.json's workerBranch)")
    s.add_argument("--model")
    s.add_argument("--pr", action="store_true", help="let Cursor open a pull request")
    s.add_argument("--wait", action="store_true", help="wait for the run and print its reply")
    s.set_defaults(fn=cmd_agent)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    args = parser().parse_args(argv)
    if hasattr(args, "command"):
        args.command = args.command + command
        if args.cmd == "run" and not args.command:
            sys.exit("run needs a command: cloud/fleet.py run NAME [options] -- CMD...")
    try:
        return args.fn(args)
    except ApiError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    sys.exit(main())
