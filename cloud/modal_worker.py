#!/usr/bin/env python3
"""Run Cursor self-hosted workers on Modal, billed per second while they run.

  up NAME... [--cpu N] [--memory GiB] [--gpu TYPE] [--idle-minutes M] [--hours H]
  status [--json]       each worker's state, hardware, $/hr and sign-in link
  login [NAME]          the sign-in link a worker is waiting on
  logs NAME             the worker's recent output
  down NAME... | --all  stop workers

A worker is one call of a Modal function in the app cryptanalysis-workers.
The call clones this repository, signs in to Cursor, runs `agent worker
--name NAME`, and returns once it has gone --idle-minutes without an agent
session, CPU or GPU load, or edits in its checkout, or after --hours (Modal
allows 24).  Agents reach it like the Runpod workers: pick NAME on
cursor.com/agents, or write `worker=NAME` in Slack or GitHub.

Signing in: with CURSOR_API_KEY in the Modal secret `cursor-worker`, a worker
uses that key.  Otherwise it runs `agent login` and publishes the link
(`status`, `login`); open it while signed in to cursor.com as the account that
should own the workers.  The sign-in is kept on the volume
cryptanalysis-workers and shared: workers waiting for a sign-in adopt the
first one completed, and later launches reuse it.  Before a worker stops, a
checkout with uncommitted or unpushed work is saved to the same volume.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
APP_NAME = "cryptanalysis-workers"
STATE_NAME = "cryptanalysis-workers"
VOLUME_NAME = "cryptanalysis-workers"
SECRET_NAME = "cursor-worker"
REPO = "https://github.com/aburan28/cryptanalysis.git"
BRANCH = "claude/cryptanalysis-repo-setup-p59kek"
MAX_HOURS = 24
PERSIST = Path("/persist")
CHECKOUT = Path("/root/cryptanalysis")
MANAGEMENT = "127.0.0.1:8787"
SIGN_IN_FILES = (".config/cursor*/auth.json", ".cursor/auth.json")
CLI_PATH = "/root/.local/bin"
# Modal's list prices (`modal billing rates`), used only for the $/hr estimate.
CPU_RATE, MEMORY_RATE = 0.0473, 0.008
GPU_RATES = {"T4": 0.59, "L4": 0.80, "A10G": 1.10, "L40S": 1.95, "A100-40GB": 2.10,
             "A100-80GB": 2.50, "RTX-PRO-6000": 3.03, "H100": 3.95, "H200": 4.54,
             "B200": 6.25}

volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True, version=2)
app = modal.App(APP_NAME)


def worker_image(kind):
    sys.path.insert(0, str(HERE))
    import modal_run
    return (modal_run.image_for(kind)
            .run_commands("curl -fsS https://cursor.com/install | bash")
            .env({"PATH": f"{CLI_PATH}:{modal_run.image_path(kind)}"})
            .add_local_file(HERE / "worker" / "idle.py", "/opt/fleet/idle.py"))


# Inside a container the images already exist; only the launching side builds them.
if modal.is_local():
    CPU_IMAGE, GPU_IMAGE = worker_image("cpu"), worker_image("cuda")
else:
    CPU_IMAGE = GPU_IMAGE = modal.Image.debian_slim()

FUNCTION = {"volumes": {str(PERSIST): volume}, "timeout": MAX_HOURS * 3600,
            "cpu": 2.0, "memory": 4096, "max_containers": 50}


@app.function(image=CPU_IMAGE, **FUNCTION)
def cpu_worker(name: str, opts: dict) -> dict:
    return serve(name, opts)


@app.function(image=GPU_IMAGE, gpu="L4", **FUNCTION)
def gpu_worker(name: str, opts: dict) -> dict:
    return serve(name, opts)


# ---- inside the container ------------------------------------------------------------

def run(*args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def signed_in():
    out = run("agent", "status", "--format", "json").stdout
    try:
        return bool(json.loads(out).get("isAuthenticated"))
    except ValueError:
        return False


def sign_in_files(home):
    return [p for pattern in SIGN_IN_FILES for p in Path(home).glob(pattern) if p.is_file()]


def copy_sign_in(source_home, target_home):
    """Copy the Cursor CLI's sign-in files from one home directory to another."""
    copied = 0
    for path in sign_in_files(source_home):
        target = Path(target_home) / path.relative_to(source_home)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


class Worker:
    def __init__(self, name, opts):
        self.name, self.opts = name, opts
        self.state = modal.Dict.from_name(STATE_NAME, create_if_missing=True)
        self.saved = PERSIST / name / "home"
        self.shared = PERSIST / "_shared" / "home"
        self.log_path = Path("/root/worker.log")
        self.started = time.time()
        self.proc = None

    def update(self, **fields):
        entry = self.state.get(self.name) or {}
        entry.update(fields, updated=time.time())
        self.state[self.name] = entry

    def tail(self, lines=40):
        try:
            return self.log_path.read_text(errors="replace").splitlines()[-lines:]
        except OSError:
            return []

    def keep_sign_in(self, share=False):
        copy_sign_in(Path.home(), self.saved)
        if share:
            copy_sign_in(Path.home(), self.shared)
        volume.commit()

    def adopt(self, home):
        return copy_sign_in(home, Path.home()) and signed_in()

    def shared_stamp(self):
        try:
            volume.reload()
        except Exception:  # reload refuses while files on the volume are open
            pass
        return max((p.stat().st_mtime for p in sign_in_files(self.shared)), default=0.0)

    def sign_in(self):
        """Sign in with the kept or shared session, else publish an `agent login` link."""
        if os.environ.get("CURSOR_API_KEY"):
            return True
        if self.adopt(self.saved) or signed_in():
            return True
        deadline = time.time() + self.opts["login_minutes"] * 60
        tried = -1.0
        while time.time() < deadline:
            stamp = self.shared_stamp()
            if stamp > tried:
                tried = stamp
                if stamp and self.adopt(self.shared):
                    self.keep_sign_in()
                    return True
            login = subprocess.Popen(["agent", "login"], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True,
                                     env={**os.environ, "NO_OPEN_BROWSER": "1"})
            for line in login.stdout:
                if "https://cursor.com/loginDeepControl" in line:
                    link = line[line.index("https://"):].split()[0]
                    self.update(state="waiting for sign-in", login_link=link)
                    break
            # Another worker's sign-in (a newer shared session) ends this wait too.
            while login.poll() is None and time.time() < deadline:
                time.sleep(10)
                if signed_in() or self.shared_stamp() > tried:
                    break
            if login.poll() is None:
                login.kill()
            if signed_in():
                self.keep_sign_in(share=True)
                return True
            time.sleep(5)
        return False

    def start_worker(self):
        labels = ["--label", "fleet=modal", "--label", f"cpus={self.opts['cpu']:g}",
                  "--label", f"mem_gb={self.opts['memory']:g}"]
        if self.opts.get("gpu"):
            labels += ["--label", f"gpu={self.opts['gpu']}"]
        command = ["agent", "worker", "--name", self.name, "--worker-dir", str(CHECKOUT),
                   "--data-dir", "/root/.cursor-worker", "--idle-release-timeout", "0",
                   "--management-addr", MANAGEMENT, *labels, "start", "--verbose"]
        log = self.log_path.open("a")
        self.proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)

    def save_unsaved(self, idle):
        if not idle.unsaved_work(CHECKOUT):
            return None
        path = PERSIST / self.name / f"unsaved-{time.strftime('%Y%m%d-%H%M%S')}.tar.gz"
        run("tar", "-czf", str(path), "--exclude=build", "--exclude=build-*", "--exclude=target",
            "-C", str(CHECKOUT.parent), CHECKOUT.name)
        volume.commit()
        return str(path)

    def serve(self):
        os.environ["FLEET_WORKDIR"] = str(CHECKOUT)
        sys.path.insert(0, "/opt/fleet")
        import idle
        gpu = run("nvidia-smi", "--query-gpu=name", "--format=csv,noheader").stdout.strip() \
            if shutil.which("nvidia-smi") else ""
        self.state.pop(f"{self.name}:stop", None)
        self.update(state="starting", started=self.started, login_link=None, reason=None,
                    gpu_name=gpu or None)
        run("git", "clone", "-q", self.opts["repo"], str(CHECKOUT), check=True)
        run("git", "-C", str(CHECKOUT), "checkout", "-q", self.opts["branch"])
        for key, value in (("user.name", "Cursor Agent"), ("user.email", "cursoragent@cursor.com")):
            run("git", "config", "--global", key, value, check=True)
        if not self.sign_in():
            self.update(state="stopped", login_link=None,
                        reason=f"nobody signed in within {self.opts['login_minutes']} minutes")
            return {"reason": "no sign-in"}
        self.update(state="connecting", login_link=None)
        self.start_worker()

        reason, restarts, last_busy, last_kept = None, 0, time.time(), time.time()
        before_cpu, before = idle.cpu_seconds(), time.monotonic()
        try:
            while reason is None:
                time.sleep(30)
                if self.proc.poll() is not None:
                    restarts += 1
                    if restarts > 5:
                        reason = f"agent worker kept exiting (last status {self.proc.returncode})"
                        break
                    self.start_worker()
                metrics = idle.worker_metrics(MANAGEMENT)
                cpu, now = idle.cpu_seconds(), time.monotonic()
                cores = max(0.0, (cpu - before_cpu) / max(1e-6, now - before))
                before_cpu, before = cpu, now
                gpu_load = idle.gpu_percent()
                busy = [r for r in (idle.agent_busy(metrics),) if r]
                if cores > idle.BUSY_CORES:
                    busy.append(f"cpu {cores:.2f} cores")
                if gpu_load is not None and gpu_load > idle.BUSY_GPU_PERCENT:
                    busy.append(f"gpu {gpu_load}%")
                if not busy and idle.recent_edit(CHECKOUT):
                    busy.append("recent edits")
                if busy:
                    last_busy = time.time()
                idle_minutes = (time.time() - last_busy) / 60
                self.update(state="in use" if metrics.get("session_active") else
                            "connected" if metrics.get("connected") else "connecting",
                            idle_minutes=round(idle_minutes, 1), busy=busy, log_tail=self.tail())
                if self.state.get(f"{self.name}:stop"):
                    reason = "stopped by `down`"
                elif idle_minutes >= self.opts["idle_minutes"]:
                    reason = f"idle for {self.opts['idle_minutes']:g} minutes"
                elif time.time() - self.started > self.opts["hours"] * 3600 - 600:
                    reason = f"reached its {self.opts['hours']:g} h limit"
                if time.time() - last_kept > 600:
                    self.keep_sign_in()
                    last_kept = time.time()
        finally:
            reason = reason or "stopped"
            if self.proc and self.proc.poll() is None:
                self.proc.send_signal(signal.SIGTERM)
                try:
                    self.proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            saved = self.save_unsaved(idle)
            self.keep_sign_in()
            self.update(state="stopped", reason=reason, saved=saved, log_tail=self.tail())
        return {"reason": reason, "saved": saved}


def serve(name, opts):
    return Worker(name, opts).serve()


# ---- the launching side -----------------------------------------------------------------

def rate(cpu, memory_gib, gpu):
    kind, _, count = (gpu or "").partition(":")
    gpus = GPU_RATES.get(kind, 0) * int(count or 1) if kind else 0
    return cpu * CPU_RATE + memory_gib * MEMORY_RATE + gpus


def state():
    return modal.Dict.from_name(STATE_NAME, create_if_missing=True)


def worker_entries(workers):
    """Worker records, without the `<name>:stop` control keys."""
    return {k: v for k, v in workers.items() if ":" not in k}


def running(entry):
    if not entry or not entry.get("call"):
        return False
    try:
        modal.FunctionCall.from_id(entry["call"]).get(timeout=0)
    except (TimeoutError, modal.exception.TimeoutError):
        return True
    except Exception:
        return False
    return False


def secrets():
    secret = modal.Secret.from_name(SECRET_NAME)
    try:
        secret.hydrate()
    except modal.exception.NotFoundError:
        return []
    return [secret]


def cmd_up(args):
    workers = state()
    with modal.enable_output():
        app.deploy()
    key = secrets()
    for name in args.names:
        if running(workers.get(name)):
            print(f"{name}: already running")
            continue
        opts = {"repo": REPO, "branch": args.branch, "cpu": args.cpu, "memory": args.memory,
                "gpu": args.gpu, "idle_minutes": args.idle_minutes, "hours": args.hours,
                "login_minutes": args.login_minutes}
        function = modal.Function.from_name(APP_NAME, "gpu_worker" if args.gpu else "cpu_worker")
        function = function.with_options(cpu=args.cpu, memory=int(args.memory * 1024),
                                         gpu=args.gpu, timeout=int(args.hours * 3600),
                                         secrets=key)
        call = function.spawn(name, opts)
        workers[name] = {"call": call.object_id, "state": "queued", "cpu": args.cpu,
                         "memory_gib": args.memory, "gpu": args.gpu,
                         "rate": round(rate(args.cpu, args.memory, args.gpu), 2),
                         "created": time.time(), "updated": time.time()}
        print(f"{name}: launched ({args.cpu:g} CPU, {args.memory:g} GiB"
              f"{', ' + args.gpu if args.gpu else ''}; about ${rate(args.cpu, args.memory, args.gpu):.2f}/hr)")
    if not key:
        print("Each worker signs in with `agent login`; `cloud/modal_worker.py login` prints the "
              "link once it is ready (about a minute).")
    return 0


def cmd_status(args):
    workers = state()
    rows = []
    for name, entry in sorted(worker_entries(workers).items()):
        alive = running(entry)
        rows.append({"name": name, **entry, "state": entry.get("state") if alive else
                     f"stopped ({entry.get('reason') or 'ended'})"})
    if args.json:
        print(json.dumps(rows, indent=1, default=str))
        return 0
    if not rows:
        print("no Modal workers yet: cloud/modal_worker.py up NAME")
        return 0
    for r in rows:
        hardware = f"{r.get('cpu', 0):g} CPU, {r.get('memory_gib', 0):g} GiB" + (
            f", {r['gpu']}" if r.get("gpu") else "")
        live = not r["state"].startswith("stopped")
        cost = f"${r.get('rate', 0):.2f}/hr" if live else "-"
        idle_minutes = f"idle {r['idle_minutes']:.0f} min" if live and r.get("idle_minutes") else ""
        print(f"{r['name']:14} {r['state'][:44]:44} {cost:>9}  {hardware}  {idle_minutes}")
        if live and r.get("login_link"):
            print(f"{'':14} sign in: {r['login_link']}")
    return 0


def cmd_login(args):
    workers = state()
    names = [args.name] if args.name else sorted(worker_entries(workers))
    found = False
    for name in names:
        entry = workers.get(name) or {}
        if entry.get("login_link") and running(entry):
            print(f"{name}: {entry['login_link']}")
            found = True
    if not found:
        print("no worker is waiting for a sign-in" + (f" ({args.name})" if args.name else ""))
    return 0


def cmd_logs(args):
    entry = state().get(args.name)
    if not entry:
        sys.exit(f"no Modal worker {args.name}")
    print("\n".join(entry.get("log_tail") or ["(no output yet)"]))
    return 0


def cmd_down(args):
    """Ask workers to stop (they save unsaved work first), then cancel stragglers."""
    workers = state()
    names = sorted(worker_entries(workers)) if args.all else args.names
    stopping = []
    for name in names:
        if running(workers.get(name)):
            workers[f"{name}:stop"] = True
            stopping.append(name)
            print(f"{name}: stopping")
        else:
            print(f"{name}: not running")
    deadline = time.time() + args.grace
    while stopping and time.time() < deadline:
        time.sleep(5)
        stopping = [n for n in stopping if running(workers.get(n))]
    for name in stopping:
        entry = workers.get(name)
        modal.FunctionCall.from_id(entry["call"]).cancel()
        workers[name] = {**entry, "state": "stopped", "reason": "cancelled by `down`",
                         "updated": time.time()}
        print(f"{name}: cancelled after {args.grace:g} s")
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("up", help="launch workers")
    s.add_argument("names", nargs="+")
    s.add_argument("--cpu", type=float, default=16, help="cores (default 16)")
    s.add_argument("--memory", type=float, default=64, help="GiB (default 64)")
    s.add_argument("--gpu", help="GPU type, e.g. L4, L40S, H100, RTX-PRO-6000 (default: none)")
    s.add_argument("--idle-minutes", type=float, default=120,
                   help="stop after this long without work (default 120)")
    s.add_argument("--hours", type=float, default=MAX_HOURS,
                   help=f"stop after this long in any case (default and maximum {MAX_HOURS})")
    s.add_argument("--login-minutes", type=float, default=45,
                   help="give up if nobody signs in within this long (default 45)")
    s.add_argument("--branch", default=BRANCH, help="branch to check out")
    s.set_defaults(fn=cmd_up)

    s = sub.add_parser("status", help="every worker's state")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("login", help="the sign-in link a worker is waiting on")
    s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("logs", help="a worker's recent output")
    s.add_argument("name")
    s.set_defaults(fn=cmd_logs)

    s = sub.add_parser("down", help="stop workers")
    s.add_argument("names", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("--grace", type=float, default=90,
                   help="seconds to let a worker save its work before cancelling it")
    s.set_defaults(fn=cmd_down)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.cmd == "up":
        if not 0 < args.hours <= MAX_HOURS:
            sys.exit(f"--hours must be in (0, {MAX_HOURS}]")
        bad = [n for n in args.names if not n.replace("-", "").isalnum()]
        if bad:
            sys.exit(f"worker names are letters, digits and dashes: {bad}")
    if args.cmd == "down" and not (args.names or args.all):
        sys.exit("down needs worker names or --all")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
