#!/usr/bin/env python3
"""A job queue on Runpod GPU runners, through cairn's host agent.

    cloud/cairn_queue.py up gpu-1                  # a runner: a GPU pod running `cairn agent`
    cloud/cairn_queue.py submit gpu-1 --out results/a.json -- \\
        'mkdir -p results && cd suite && cargo run --release --bin ca-ic -- \\
         run --degree 23 --curve-a 1 --out ../results/a.json'
    cloud/cairn_queue.py jobs gpu-1                # queued, running and done, with receipts
    cloud/cairn_queue.py wait gpu-1 JOB...         # until each one has a receipt
    cloud/cairn_queue.py fetch gpu-1 JOB...        # outputs into this checkout, records beside
    cloud/cairn_queue.py hosts gpu-1               # what registered with the runner's node
    cloud/cairn_queue.py logs gpu-1 [agent|node|boot]
    cloud/cairn_queue.py list                      # runner pods
    cloud/cairn_queue.py down gpu-1

A runner is a Runpod pod (cloud/runpod_pod.py) whose start runs
cloud/cairn_runner.sh: cairn's host agent from a pinned release, registering
the machine with a cairn node every minute and running the job specs in its
spool one at a time, each to a receipt.  `submit` ships this checkout (edits
included; once per distinct tree), writes a cairn job spec whose command
unpacks it into the runner's checkout, sources cloud/pod_env.sh (Rust,
NVRTC) and runs CMD under cloud/job_runner.sh, and queues the spec with
`cairn agent submit`.  `fetch` merges each job's --out paths into this
checkout and keeps its receipt, spec, logs and status.json under
.cairn-jobs/RUNNER/JOB.

Jobs run unconfined on the pod, which is their only jail; GPU_NOTE says why
they declare no GPU and still use the pod's.  Needs RUNPOD_API_KEY and the
SSH key runpod_pod.py uses.
"""

import argparse
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import runpod_pod  # noqa: E402
import tree  # noqa: E402

CAIRN_VERSION = "1.17.0"
RUNNER = "/root/runner"
SPOOL = f"{RUNNER}/agent"
PRIVATE_NODE = "http://127.0.0.1:8080"
RECORDS = REPO / ".cairn-jobs"
# Every job runs these two from its own tree, so a subset always carries them.
JOB_SCRIPTS = ("cloud/job_runner.sh", "cloud/pod_env.sh")
DEFAULT_TIMEOUT = 4 * 3600

GPU_NOTE = ("Unconfined (sandbox none) on a Runpod pod, a container with no engine inside: "
            "cairn passes a GPU only to a job an engine runs, so the spec asks for none, "
            "and the job uses the pod's GPU directly.")

# The command of every job.  The job's tree replaces the runner's checkout
# (RUNNER_CHECKOUT, which jobs inherit from the agent) except the suite's
# build tree, which stays so builds are warm; then the toolchain, then
# job_runner.sh, which runs JOB_CMD and packs JOB_OUTS and a status.json into
# the job's out/ directory.
JOB_SCRIPT = r"""
set -euo pipefail
work=${RUNNER_CHECKOUT:-/root/runner/checkout}
mkdir -p "$work"
find "$work" -mindepth 1 -maxdepth 1 ! -name suite -exec rm -rf {} +
if [ -d "$work/suite" ]; then
  find "$work/suite" -mindepth 1 -maxdepth 1 ! -name target -exec rm -rf {} +
fi
tar --no-same-owner -xzf "$CAIRN_LAB_MOUNT_IN_TREE_TAR_GZ" -C "$work"
cd "$work"
source cloud/pod_env.sh
JOB_DIR=$CAIRN_LAB_OUT JOB_WORKDIR=$work exec bash cloud/job_runner.sh
""".strip()


# The jobs a runner still holds for somebody: queued, running, or done and not
# yet fetched.  Its idle watchdog keeps it up for the same jobs.
LEFT_SCRIPT = r"""
cd /root/runner/agent/jobs 2>/dev/null || exit 0
for f in queue/*.json; do [ -e "$f" ] && basename "$f" .json; done
for d in running/*/; do [ -d "$d" ] && basename "$d"; done
for d in done/*/; do [ -d "$d" ] && [ ! -e "$d.fetched" ] && basename "$d"; done
true
""".strip()


def new_job_id():
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + os.urandom(2).hex()


def tree_files(root, only=()):
    """The checkout's files, or those under `only` plus JOB_SCRIPTS."""
    files = tree.checkout_files(root)
    if not only:
        return files
    keep = [p.strip("/") for p in only]
    return [f for f in files
            if f in JOB_SCRIPTS or any(f == k or f.startswith(k + "/") for k in keep)]


def tree_key(root, files):
    """Names a tree by its files' paths, sizes, modes and mtimes: an edit is a new tree."""
    digest = hashlib.sha256()
    for name in files:
        st = os.lstat(Path(root) / name)
        digest.update(f"{name}\0{st.st_size}\0{st.st_mode}\0{st.st_mtime_ns}\n".encode())
    return digest.hexdigest()[:20]


def job_spec(job_id, key, command, outs=(), changed=False, timeout=DEFAULT_TIMEOUT, git=None,
             objective=None, task=None):
    """The cairn job spec (cairn's docs/agent.md) that runs `command` on tree `key`."""
    env = {"JOB_ID": job_id, "JOB_CMD": command, "JOB_OUTS": "\n".join(outs),
           "JOB_CHANGED": "1" if changed else "0", "JOB_TREE": key}
    if git:
        env.update(JOB_COMMIT=git.get("commit") or "", JOB_BRANCH=git.get("branch") or "",
                   JOB_DIRTY="1" if git.get("dirty") else "0")
    spec = {"id": job_id, "rootfs": "/", "sandbox": "none", "argv": ["bash", "-c", JOB_SCRIPT],
            "env": env, "inputs": [{"source": f"{RUNNER}/trees/{key}.tar.gz",
                                    "target": "/in/tree.tar.gz"}],
            "timeout_seconds": timeout, "network": True, "gpus": 0, "pids": 0, "note": GPU_NOTE}
    if objective:
        spec.update(objective_id=objective, task=task)
    return spec


def runner_env(args):
    """The pod variables that make a runpod_pod.py pod a runner."""
    env = {"POD_BOOT_B64": base64.b64encode((HERE / "cairn_runner.sh").read_bytes()).decode(),
           "CAIRN_RUNNER_NAME": args.name, "CAIRN_VERSION": args.cairn_version,
           "RUNNER_IDLE_MINUTES": str(args.idle_minutes)}
    if args.node:
        env["CAIRN_AGENT_NODES"] = ",".join(args.node)
    return env


def job_state(listing, job_id):
    """('queued' | 'running' | 'done' | 'refused' | 'unknown', receipt or None)."""
    if job_id in listing.get("queued", []):
        return "queued", None
    if job_id in listing.get("running", []):
        return "running", None
    for entry in listing.get("done", []):
        if entry["id"] == job_id and entry.get("receipt"):
            return "done", entry["receipt"]
        if entry["id"] in (f"{job_id}.duplicate", f"{job_id}.json.invalid"):
            return "refused", None
    return "unknown", None


def receipt_line(receipt):
    if receipt.get("error"):
        return f"could not run: {receipt['error']}"
    how = "timed out" if receipt.get("timed_out") else f"exit {receipt.get('exit_status')}"
    return (f"{how} after {receipt.get('wall_ms', 0) / 1000:.1f} s on {receipt.get('host')} "
            f"under {receipt.get('sandbox')}")


# ---- the pod ----------------------------------------------------------------------------

def ssh_environ():
    # ssh forwards LANG/LC_*; the pods lack most locales and bash warns about each one.
    return {k: v for k, v in os.environ.items() if k != "LANG" and not k.startswith("LC_")}


def remote(pod, script, data=None, capture=False):
    return subprocess.run([*runpod_pod.ssh_args(pod), f"bash -c {shlex.quote(script)}"],
                          input=data, capture_output=capture, env=ssh_environ(), check=False)


def runner(name):
    pod = runpod_pod.find(name)
    if pod is None:
        sys.exit(f"no runner named {name} (`up` makes one)")
    if pod.get("desiredStatus") != "RUNNING":
        sys.exit(f"{name} is {pod.get('desiredStatus')}; `up {name}` starts it")
    return pod


def listing(pod):
    out = remote(pod, f"cairn agent jobs --data-dir {SPOOL} --json", capture=True)
    if out.returncode != 0:
        sys.exit(f"cairn agent jobs failed on {pod['name']}: {out.stderr.decode().strip()}")
    return json.loads(out.stdout)


def wait_for_agent(pod, seconds=600):
    """Until the runner has cairn and its spool; the boot log if it never does."""
    deadline = time.time() + seconds
    check = f"command -v cairn >/dev/null && test -d {SPOOL}/jobs/queue"
    while time.time() < deadline:
        if remote(pod, check, capture=True).returncode == 0:
            return True
        time.sleep(5)
    remote(pod, "tail -n 30 /root/pod-boot.log")
    return False


# ---- commands ---------------------------------------------------------------------------

def cmd_up(args):
    pod = runpod_pod.find(args.name)
    if pod and pod.get("desiredStatus") == "RUNNING":
        print(f"{args.name} is running ({pod['id']})")
    elif pod:
        print(f"starting {args.name} ({pod['id']}, {pod.get('desiredStatus')})", flush=True)
        runpod_pod.api("POST", f"{runpod_pod.REST}/pods/{pod['id']}/start")
        deadline = time.time() + args.wait
        while not (pod.get("publicIp") and (pod.get("portMappings") or {}).get("22")):
            if time.time() > deadline:
                sys.exit(f"{args.name} did not come back; `down` it and `up` a new one")
            time.sleep(10)
            pod = runpod_pod.api("GET", f"{runpod_pod.REST}/pods/{pod['id']}")
    else:
        pod = runpod_pod.create(args, runner_env(args))
    if not wait_for_agent(pod):
        print(f"the agent did not start on {args.name}; see the log above", file=sys.stderr)
        return 3
    print(f"{args.name} is ready: `submit {args.name} -- CMD` queues a job", flush=True)
    return 0


def cmd_submit(args):
    command = " ".join(args.command)
    if not command:
        sys.exit("submit needs a command after --")
    pod = runner(args.name)
    files = tree_files(REPO, args.only)
    key = tree_key(REPO, files)
    remote_tree = f"{RUNNER}/trees/{key}.tar.gz"
    if remote(pod, f"test -s {remote_tree}", capture=True).returncode == 0:
        print(f"tree {key} is already on {args.name}", file=sys.stderr)
    else:
        data, summary = tree.pack(REPO, names=files)
        print(f"shipping {summary['files']} files, {summary['bytes'] / 1e6:.1f} MB as tree {key}",
              file=sys.stderr, flush=True)
        for skipped in summary["skipped"]:
            print(f"  skipped large file {skipped}", file=sys.stderr)
        script = f"mkdir -p {RUNNER}/trees && cat > {remote_tree}.part && mv {remote_tree}.part {remote_tree}"
        if remote(pod, script, data=data).returncode != 0:
            sys.exit("could not ship the tree")
    job_id = args.id or new_job_id()
    spec = job_spec(job_id, key, command, args.out, args.changed, args.timeout,
                    tree.git_state(REPO), args.objective, args.task)
    path = f"{RUNNER}/specs/{job_id}.json"
    script = f"mkdir -p {RUNNER}/specs && cat > {path} && cairn agent submit {path} --data-dir {SPOOL}"
    out = remote(pod, script, data=json.dumps(spec).encode(), capture=True)
    if out.returncode != 0:
        sys.exit(f"cairn agent submit refused {job_id}: {out.stderr.decode().strip()}")
    print(job_id)
    return 0


def cmd_jobs(args):
    pod = runner(args.name)
    return remote(pod, f"cairn agent jobs --data-dir {SPOOL}" + (" --json" if args.json else "")
                  ).returncode


def cmd_wait(args):
    pod = runner(args.name)
    pending, seen, outcome = list(args.ids), {}, 0
    deadline = time.time() + args.timeout if args.timeout else None
    while pending:
        jobs = listing(pod)
        for job_id in list(pending):
            state, receipt = job_state(jobs, job_id)
            # A job moving between spool directories can be in neither for
            # one listing; only a second miss means there is no such job.
            if state == "unknown" and seen.get(job_id) != "missing":
                seen[job_id] = "missing"
                continue
            if state != seen.get(job_id):
                seen[job_id] = state
                print(f"{job_id}: {receipt_line(receipt) if receipt else state}", flush=True)
            if state in ("done", "refused", "unknown"):
                pending.remove(job_id)
                if state != "done" or receipt.get("error"):
                    outcome = max(outcome, 3)
                elif not receipt.get("succeeded"):
                    outcome = max(outcome, 1)
        if pending:
            if deadline and time.time() > deadline:
                print(f"still waiting for {' '.join(pending)}", file=sys.stderr)
                return 2
            time.sleep(args.interval)
    return outcome


def cmd_fetch(args):
    pod = runner(args.name)
    jobs, rc = listing(pod), 0
    for job_id in args.ids:
        state, receipt = job_state(jobs, job_id)
        if state != "done":
            print(f"{job_id}: {state}, nothing to fetch yet", file=sys.stderr)
            rc = 1
            continue
        done = f"{SPOOL}/jobs/done/{job_id}"
        records = Path(args.into or RECORDS / args.name) / job_id
        records.mkdir(parents=True, exist_ok=True)
        pack = (f"cd {done} && tar -czf - receipt.json job.json stdout stderr "
                "$(ls out/status.json out/log.txt out/outputs.txt 2>/dev/null)")
        got = remote(pod, pack, capture=True)
        if got.returncode != 0:
            print(f"{job_id}: could not read its records", file=sys.stderr)
            rc = 1
            continue
        subprocess.run(["tar", "-xzf", "-", "-C", str(records)], input=got.stdout, check=True)
        outputs = remote(pod, f"cat {done}/out/out.tar.gz 2>/dev/null", capture=True).stdout
        written = tree.merge_outputs(outputs, REPO, job_id, {}) if outputs else []
        for path in written:
            print(f"  fetched {path}", file=sys.stderr)
        remote(pod, f"touch {done}/.fetched")
        print(f"{job_id}: {receipt_line(receipt)}; records in {records}")
        rc = rc or (0 if receipt.get("succeeded") else 1)
    return rc


def cmd_hosts(args):
    pod = runner(args.name)
    nodes = (pod.get("env") or {}).get("CAIRN_AGENT_NODES") or PRIVATE_NODE
    for node in nodes.split(","):
        url = f"{node.rstrip('/')}/hosts"
        if node == PRIVATE_NODE:
            raw = remote(pod, f"curl -fsS {url}", capture=True).stdout
        else:
            with urllib.request.urlopen(url, timeout=20) as response:
                raw = response.read()
        roster = json.loads(raw)
        print(f"{node}: {roster.get('live', 0)} live, {roster.get('gpus', 0)} GPUs")
        for host in roster.get("hosts", []):
            gpus = [g.get("model") for g in (host.get("hardware") or {}).get("gpus", [])]
            print(f"  {host.get('host')}: {host.get('status')}, {host.get('agent')}, "
                  f"gpus {gpus}, jobs {host.get('jobs')}")
    return 0


def cmd_logs(args):
    pod = runner(args.name)
    path = {"agent": f"{RUNNER}/agent.log", "node": f"{RUNNER}/node.log",
            "boot": "/root/pod-boot.log"}[args.which]
    return remote(pod, f"tail -n {args.lines} {path}").returncode


def cmd_list(args):
    for pod in runpod_pod.pods():
        if "CAIRN_RUNNER_NAME" in (pod.get("env") or {}):
            print(f"{pod['id']}  {pod.get('name')}  {pod.get('desiredStatus')}  "
                  f"{pod.get('gpuCount') or 0} GPU  {pod.get('vcpuCount')} vCPU  "
                  f"{pod.get('costPerHr')} $/hr")
    return 0


def cmd_down(args):
    pod = runpod_pod.need(args.name)
    if pod.get("desiredStatus") == "RUNNING" and not args.force:
        left = remote(pod, LEFT_SCRIPT, capture=True).stdout.decode().split()
        if left:
            sys.exit(f"{args.name} still has {' '.join(left)} queued, running or unfetched; "
                     "fetch them or pass --force")
    runpod_pod.api("DELETE", f"{runpod_pod.REST}/pods/{pod['id']}")
    print(f"deleted {pod['id']} ({args.name})")
    return 0


def parse(argv=None):
    """Arguments; for `submit`, whatever follows `--` is the command."""
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        cut = argv.index("--")
        argv, command = argv[:cut], argv[cut + 1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("up", help="create or start a runner")
    up.add_argument("name")
    runpod_pod.add_pod_options(up)
    up.set_defaults(max_hours=24.0)
    up.add_argument("--node", action="append", default=[], metavar="URL",
                    help="a cairn node to register with (default: a private one on the pod)")
    up.add_argument("--idle-minutes", type=int, default=60,
                    help="stop the pod after this long with nothing queued, running or "
                         "unfetched (0: never)")
    up.add_argument("--cairn-version", default=CAIRN_VERSION)

    submit = sub.add_parser("submit", help="queue CMD on a runner")
    submit.add_argument("name")
    submit.add_argument("--id", help="the job id (default: a new timestamped one)")
    submit.add_argument("--out", action="append", default=[], metavar="PATH",
                        help="a path relative to the repository to bring back")
    submit.add_argument("--changed", action="store_true",
                        help="also bring back every file the command wrote")
    submit.add_argument("--only", action="append", default=[], metavar="PATH",
                        help="ship only these paths of the checkout")
    submit.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SECONDS")
    submit.add_argument("--objective", help="a cairn objective id the node holds, to lease "
                                            "--task on while the job runs")
    submit.add_argument("--task")

    for name, help_text in (("jobs", "the runner's queue"), ("hosts", "its node's roster")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("name")
        if name == "jobs":
            p.add_argument("--json", action="store_true")
    wait = sub.add_parser("wait", help="until each job has a receipt; exits 0 when all "
                          "succeeded, 1 when one failed, 2 on --timeout, 3 when one could "
                          "not run or does not exist")
    wait.add_argument("name")
    wait.add_argument("ids", nargs="+")
    wait.add_argument("--interval", type=float, default=10.0)
    wait.add_argument("--timeout", type=float, default=0.0, help="seconds; 0 waits forever")
    fetch = sub.add_parser("fetch", help="bring finished jobs back")
    fetch.add_argument("name")
    fetch.add_argument("ids", nargs="+")
    fetch.add_argument("--into", help=f"records directory (default {RECORDS.name}/RUNNER)")
    logs = sub.add_parser("logs")
    logs.add_argument("name")
    logs.add_argument("which", nargs="?", default="agent", choices=["agent", "node", "boot"])
    logs.add_argument("-n", "--lines", type=int, default=50)
    sub.add_parser("list")
    down = sub.add_parser("down")
    down.add_argument("name")
    down.add_argument("--force", action="store_true",
                      help="delete it even with jobs queued, running or unfetched")
    args = ap.parse_args(argv)
    if args.cmd == "up" and args.cpu and args.gpu:
        ap.error("--cpu and --gpu are exclusive")
    if args.cmd == "submit" and bool(args.objective) != bool(args.task):
        ap.error("--objective and --task go together")
    args.command = command
    return args


def main(argv=None):
    args = parse(argv)
    return {"up": cmd_up, "submit": cmd_submit, "jobs": cmd_jobs, "wait": cmd_wait,
            "fetch": cmd_fetch, "hosts": cmd_hosts, "logs": cmd_logs, "list": cmd_list,
            "down": cmd_down}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
