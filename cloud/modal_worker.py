#!/usr/bin/env python3
"""Run Cursor self-hosted workers on Modal, billed per second while they run.

  up NAME... [--cpu N] [--memory GiB] [--gpu TYPE] [--idle-minutes M] [--hours H]
  status [--json]       the sign-in page, and each worker's state, hardware and $/hr
  login                 the sign-in page (and any live sign-in links)
  logs NAME             the worker's recent output
  down NAME... | --all  stop workers (--all also ends a pending sign-in)

A worker is one call of a Modal function in the app cryptanalysis-workers.
The call clones this repository, signs in to Cursor, runs `agent worker
--name NAME`, and returns once it has gone --idle-minutes without an agent
session, CPU or GPU load, or edits in its checkout, or after --hours (Modal
allows 24).  Agents reach it like the Runpod workers: pick NAME on
cursor.com/agents, or write `worker=NAME` in Slack or GitHub.

Signing in: with CURSOR_API_KEY in the Modal secret `cursor-worker`, workers
use that key.  Otherwise the account that should own them signs in once on
the sign-in page `up` prints.  Until then `up` only queues workers: a small
`signin` call (a quarter of a core) keeps an `agent login` link live for up to
24 hours, the page redirects to it, and the queued workers launch when the
sign-in completes.  The sign-in is kept on the volume cryptanalysis-workers,
so later launches start at once.  Before a worker stops, a checkout with
uncommitted or unpushed work is archived to the same volume.
"""
import argparse
import hmac
import json
import os
import secrets as tokens
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
PAGE_LABEL = "cryptanalysis-signin"
SIGNIN_KEY, TOKEN_KEY = "_signin", "_token"
REPO = "https://github.com/aburan28/cryptanalysis.git"
BRANCH = "claude/cryptanalysis-repo-setup-p59kek"
MAX_HOURS = 24
PERSIST = Path("/persist")
SHARED = PERSIST / "_shared" / "home"
CHECKOUT = Path("/root/cryptanalysis")
MANAGEMENT = "127.0.0.1:8787"
# `agent status` reads ~/.config/cursor/auth.json on Linux (strace, CLI 2026.09.23).
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
WEB_IMAGE = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi[standard]")

FUNCTION = {"volumes": {str(PERSIST): volume}, "timeout": MAX_HOURS * 3600,
            "cpu": 2.0, "memory": 4096, "max_containers": 50}


@app.function(image=CPU_IMAGE, **FUNCTION)
def cpu_worker(name: str, request: dict) -> dict:
    return Worker(name, request).serve()


@app.function(image=GPU_IMAGE, gpu="L4", **FUNCTION)
def gpu_worker(name: str, request: dict) -> dict:
    return Worker(name, request).serve()


@app.function(image=CPU_IMAGE, volumes={str(PERSIST): volume}, timeout=MAX_HOURS * 3600,
              cpu=0.25, memory=512, max_containers=1)
def signin() -> dict:
    return run_signin()


@app.function(image=WEB_IMAGE)
@modal.fastapi_endpoint(method="GET", label=PAGE_LABEL)
def signin_page(k: str = ""):
    return render_page(k)


# ---- signing in (inside a container) ------------------------------------------------------

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


def adopt(home):
    return bool(copy_sign_in(home, Path.home())) and signed_in()


def keep_sign_in(saved=None, share=False):
    for target in ([saved] if saved else []) + ([SHARED] if share else []):
        copy_sign_in(Path.home(), target)
    volume.commit()


def shared_stamp():
    try:
        volume.reload()
    except Exception:  # reload refuses while files on the volume are open
        pass
    return max((p.stat().st_mtime for p in sign_in_files(SHARED)), default=0.0)


def sign_in(update, minutes, saved=None):
    """Sign in with a kept or shared session, else run `agent login` attempts.

    Each attempt's link (valid for about 24 minutes) is announced through
    update(state=..., login_link=...).  A sign-in completed by any other call
    (a newer shared session) ends the wait too.  Returns True once signed in.
    """
    if os.environ.get("CURSOR_API_KEY"):
        return True
    if (saved and adopt(saved)) or signed_in():
        return True
    deadline = time.time() + minutes * 60
    tried = -1.0
    while time.time() < deadline:
        stamp = shared_stamp()
        if stamp > tried:
            tried = stamp
            if stamp and adopt(SHARED):
                keep_sign_in(saved)
                return True
        login = subprocess.Popen(["agent", "login"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 env={**os.environ, "NO_OPEN_BROWSER": "1"})
        for line in login.stdout:
            if "https://cursor.com/loginDeepControl" in line:
                link = line[line.index("https://"):].split()[0]
                update(state="waiting for sign-in", login_link=link)
                break
        while login.poll() is None and time.time() < deadline:
            time.sleep(10)
            if signed_in() or shared_stamp() > tried:
                break
        if login.poll() is None:
            login.kill()
        if signed_in():
            keep_sign_in(saved, share=True)
            return True
        time.sleep(5)
    return False


def run_signin():
    workers = state()

    def update(**fields):
        entry = workers.get(SIGNIN_KEY) or {}
        entry.update(fields, updated=time.time())
        workers[SIGNIN_KEY] = entry

    update(state="starting", login_link=None, started=time.time())
    if not sign_in(update, MAX_HOURS * 60 - 10):
        update(state="expired", login_link=None)
        return {"signed_in": False}
    update(state="signed in", login_link=None)
    launched = launch_pending(workers)
    update(launched=launched)
    return {"signed_in": True, "launched": launched}


# ---- a worker (inside a container) -------------------------------------------------------------

class Worker:
    def __init__(self, name, request):
        self.name, self.request = name, request
        self.state = state()
        self.saved = PERSIST / name / "home"
        self.log_path = Path("/root/worker.log")
        self.started = time.time()
        self.proc = None
        self.gpu_name = ""

    def update(self, **fields):
        entry = self.state.get(self.name) or {}
        entry.update(fields, updated=time.time())
        self.state[self.name] = entry

    def tail(self, lines=40):
        try:
            return self.log_path.read_text(errors="replace").splitlines()[-lines:]
        except OSError:
            return []

    def start_worker(self):
        labels = ["--label", "fleet=modal", "--label", f"cpus={self.request['cpu']:g}",
                  "--label", f"mem_gb={self.request['memory']:g}"]
        if self.request.get("gpu"):
            labels += ["--label", f"gpu={self.request['gpu']}"]
        command = ["agent", "worker", "--name", self.name, "--worker-dir", str(CHECKOUT),
                   "--data-dir", "/root/.cursor-worker", "--idle-release-timeout", "0",
                   "--management-addr", MANAGEMENT, *labels, "start", "--verbose"]
        # The same machine description the Runpod pods give their agents (AGENTS.md).
        env = {**os.environ, "FLEET_WORKER_NAME": self.name,
               "FLEET_CPUS": str(int(self.request["cpu"])),
               "FLEET_MEM_GB": f"{self.request['memory']:g}",
               "FLEET_GPU": self.gpu_name, "FLEET_SCRATCH": "/root"}
        log = self.log_path.open("a")
        self.proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)

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
        self.gpu_name = run("nvidia-smi", "--query-gpu=name", "--format=csv,noheader").stdout \
            .strip() if shutil.which("nvidia-smi") else ""
        self.state.pop(f"{self.name}:stop", None)
        self.update(state="starting", started=self.started, login_link=None, reason=None,
                    gpu_name=self.gpu_name or None)
        run("git", "clone", "-q", self.request["repo"], str(CHECKOUT), check=True)
        run("git", "-C", str(CHECKOUT), "checkout", "-q", self.request["branch"])
        for key, value in (("user.name", "Cursor Agent"), ("user.email", "cursoragent@cursor.com")):
            run("git", "config", "--global", key, value, check=True)
        if not sign_in(self.update, self.request["login_minutes"], self.saved):
            self.update(state="stopped", login_link=None,
                        reason=f"nobody signed in within {self.request['login_minutes']:g} minutes")
            return {"reason": "no sign-in"}
        self.update(state="connecting", login_link=None)
        self.start_worker()

        reason, restarts, last_busy, last_kept = None, 0, time.time(), time.time()
        ready = time.time()
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
                if not busy and idle.recent_edit(CHECKOUT, since=ready):
                    busy.append("recent edits")
                if busy:
                    last_busy = time.time()
                idle_minutes = (time.time() - last_busy) / 60
                self.update(state="in use" if metrics.get("session_active") else
                            "connected" if metrics.get("connected") else "connecting",
                            idle_minutes=round(idle_minutes, 1), busy=busy, log_tail=self.tail())
                if self.state.get(f"{self.name}:stop"):
                    reason = "stopped by `down`"
                elif idle_minutes >= self.request["idle_minutes"]:
                    reason = f"idle for {self.request['idle_minutes']:g} minutes"
                elif time.time() - self.started > self.request["hours"] * 3600 - 600:
                    reason = f"reached its {self.request['hours']:g} h limit"
                if time.time() - last_kept > 600:
                    keep_sign_in(self.saved)
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
            keep_sign_in(self.saved)
            self.update(state="stopped", reason=reason, saved=saved, log_tail=self.tail())
        return {"reason": reason, "saved": saved}


# ---- shared by both sides ------------------------------------------------------------------------

def state():
    return modal.Dict.from_name(STATE_NAME, create_if_missing=True)


def worker_entries(workers):
    """Worker records, without the sign-in record and `<name>:stop` control keys."""
    return {k: v for k, v in dict(workers.items()).items() if ":" not in k and not k.startswith("_")}


def rate(cpu, memory_gib, gpu):
    kind, _, count = (gpu or "").partition(":")
    gpus = GPU_RATES.get(kind, 0) * int(count or 1) if kind else 0
    return cpu * CPU_RATE + memory_gib * MEMORY_RATE + gpus


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


def spawn_worker(name, request):
    function = modal.Function.from_name(APP_NAME, "gpu_worker" if request["gpu"] else "cpu_worker")
    function = function.with_options(cpu=request["cpu"], memory=int(request["memory"] * 1024),
                                     gpu=request["gpu"], timeout=int(request["hours"] * 3600),
                                     secrets=secrets())
    return function.spawn(name, request)


def launch_pending(workers):
    launched = []
    for name, entry in worker_entries(workers).items():
        if entry.get("state") == "pending":
            call = spawn_worker(name, entry["request"])
            workers[name] = {**entry, "call": call.object_id, "state": "queued",
                             "updated": time.time()}
            launched.append(name)
    return launched


def render_page(token):
    from fastapi.responses import HTMLResponse, RedirectResponse
    workers = state()
    expected = workers.get(TOKEN_KEY) or ""
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        return HTMLResponse("not found", status_code=404)
    entries = worker_entries(workers)
    links = [e.get("login_link") for e in [workers.get(SIGNIN_KEY) or {}, *entries.values()]
             if e.get("login_link") and running(e)]
    if links:
        return RedirectResponse(links[0], status_code=302)
    # Queued workers but no live sign-in (the last one lapsed): start another.
    preparing = any(e.get("state") == "pending" for e in entries.values())
    if preparing:
        ensure_signin(workers)
    rows = "".join(f"<tr><td>{name}</td><td>{e.get('state')}</td><td>{e.get('cpu', 0):g} CPU, "
                   f"{e.get('memory_gib', 0):g} GiB{', ' + e['gpu'] if e.get('gpu') else ''}</td></tr>"
                   for name, e in sorted(entries.items()))
    message = ("Preparing a sign-in link; this page opens it in a few seconds." if preparing
               else f"Sign-in: {(workers.get(SIGNIN_KEY) or {}).get('state', 'not started')}.")
    return HTMLResponse(
        "<!doctype html><meta name=viewport content='width=device-width'>"
        f"<meta http-equiv=refresh content={5 if preparing else 30}>"
        f"<title>cryptanalysis workers</title><h3>Cursor workers on Modal</h3><p>{message}</p>"
        f"<table border=1 cellpadding=4>{rows}</table>")


# ---- the launching side -----------------------------------------------------------------------------

def have_shared_sign_in():
    try:
        return any(e.path.endswith("auth.json")
                   for e in volume.listdir("/_shared/home", recursive=True))
    except Exception:  # the directory does not exist before the first sign-in
        return False


def page_url(workers):
    token = workers.get(TOKEN_KEY)
    if not token:
        token = tokens.token_urlsafe(16)
        workers[TOKEN_KEY] = token
    return f"{modal.Function.from_name(APP_NAME, 'signin_page').get_web_url()}?k={token}"


def ensure_signin(workers):
    if running(workers.get(SIGNIN_KEY)):
        return
    call = modal.Function.from_name(APP_NAME, "signin").spawn()
    workers[SIGNIN_KEY] = {"call": call.object_id, "state": "starting", "updated": time.time()}


def cmd_up(args):
    workers = state()
    with modal.enable_output():
        app.deploy()
    signed = bool(secrets()) or have_shared_sign_in()
    for name in args.names:
        entry = workers.get(name) or {}
        if running(entry) or entry.get("state") == "pending":
            print(f"{name}: already {entry.get('state')}")
            continue
        request = {"repo": REPO, "branch": args.branch, "cpu": args.cpu, "memory": args.memory,
                   "gpu": args.gpu, "idle_minutes": args.idle_minutes, "hours": args.hours,
                   "login_minutes": args.login_minutes}
        cost = rate(args.cpu, args.memory, args.gpu)
        entry = {"state": "pending", "request": request, "cpu": args.cpu,
                 "memory_gib": args.memory, "gpu": args.gpu, "rate": round(cost, 2),
                 "created": time.time(), "updated": time.time()}
        hardware = f"{args.cpu:g} CPU, {args.memory:g} GiB{', ' + args.gpu if args.gpu else ''}"
        if signed:
            entry.update(call=spawn_worker(name, request).object_id, state="queued")
            print(f"{name}: launched ({hardware}; about ${cost:.2f}/hr)")
        else:
            print(f"{name}: queued until someone signs in ({hardware}; about ${cost:.2f}/hr once running)")
        workers[name] = entry
    if not signed:
        ensure_signin(workers)
        if have_shared_sign_in():  # a sign-in finished while these were being queued
            launch_pending(workers)
        print(f"\nSign in once, as the Cursor account that should own the workers:\n"
              f"  {page_url(workers)}\nThe page stays valid; the queued workers launch after "
              f"the sign-in, and later launches reuse it.")
    return 0


def cmd_status(args):
    workers = state()
    rows = []
    for name, entry in sorted(worker_entries(workers).items()):
        live = entry.get("state") == "pending" or running(entry)
        rows.append({"name": name, **entry, "live": live,
                     "state": entry.get("state") if live else
                     f"stopped ({entry.get('reason') or 'ended'})"})
    signin_entry = workers.get(SIGNIN_KEY) or {}
    if args.json:
        print(json.dumps({"signin": signin_entry, "workers": rows}, indent=1, default=str))
        return 0
    if signin_entry:
        alive = running(signin_entry)
        final = signin_entry.get("state") in ("signed in", "expired", "cancelled")
        waiting = alive and signin_entry.get("state") == "waiting for sign-in"
        print(f"sign-in: {signin_entry.get('state') if alive or final else 'ended'}"
              + (f"  ->  {page_url(workers)}" if waiting else ""))
    if not rows:
        print("no Modal workers yet: cloud/modal_worker.py up NAME")
        return 0
    for r in rows:
        hardware = f"{r.get('cpu', 0):g} CPU, {r.get('memory_gib', 0):g} GiB" + (
            f", {r['gpu']}" if r.get("gpu") else "")
        cost = f"${r.get('rate', 0):.2f}/hr" if r["live"] and r["state"] != "pending" else "-"
        idle_minutes = f"idle {r['idle_minutes']:.0f} min" if r["live"] and r.get("idle_minutes") else ""
        print(f"{r['name']:14} {r['state'][:44]:44} {cost:>9}  {hardware}  {idle_minutes}")
    return 0


def cmd_login(args):
    workers = state()
    if args.new_token:
        workers.pop(TOKEN_KEY, None)
    print(f"sign-in page: {page_url(workers)}")
    entries = [(SIGNIN_KEY, workers.get(SIGNIN_KEY) or {}), *worker_entries(workers).items()]
    for name, entry in entries:
        if entry.get("login_link") and running(entry):
            print(f"  {name} is waiting: {entry['login_link']}")
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
    entries = worker_entries(workers)
    names = sorted(entries) if args.all else args.names
    stopping = []
    for name in names:
        entry = entries.get(name) or {}
        if entry.get("state") == "pending":
            workers[name] = {**entry, "state": "stopped", "reason": "cancelled before launch"}
            print(f"{name}: cancelled before launch")
        elif running(entry):
            workers[f"{name}:stop"] = True
            stopping.append(name)
            print(f"{name}: stopping")
        else:
            print(f"{name}: not running")
    if args.all and running(workers.get(SIGNIN_KEY)):
        modal.FunctionCall.from_id(workers[SIGNIN_KEY]["call"]).cancel()
        workers[SIGNIN_KEY] = {**workers[SIGNIN_KEY], "state": "cancelled", "login_link": None}
        print("sign-in: cancelled")
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
                   help="a worker whose shared sign-in has lapsed publishes its own link "
                        "for this long before giving up (default 45)")
    s.add_argument("--branch", default=BRANCH, help="branch to check out")
    s.set_defaults(fn=cmd_up)

    s = sub.add_parser("status", help="every worker's state")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("login", help="the sign-in page")
    s.add_argument("--new-token", action="store_true",
                   help="replace the page's secret, so earlier copies of its link stop working")
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
        bad = [n for n in args.names if not n.replace("-", "").isalnum() or n.startswith("_")]
        if bad:
            sys.exit(f"worker names are letters, digits and dashes: {bad}")
    if args.cmd == "down" and not (args.names or args.all):
        sys.exit("down needs worker names or --all")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
