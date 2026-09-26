#!/usr/bin/env python3
"""Stop this pod after FLEET_IDLE_STOP_MINUTES without work.

boot.sh runs this in the tmux session `fleet-idle` when the limit is positive.
A minute counts as busy when any of these hold:

* the Cursor worker has an agent session (its own /metrics on the
  management address),
* the container used more than BUSY_CORES of CPU,
* a GPU was more than BUSY_GPU_PERCENT utilized,
* someone is logged in over SSH,
* a `cloud/fleet.py run` job is still running,
* a file in the agents' checkout (or one of its worktrees) changed recently.

The pod is stopped, not terminated, and `cloud/fleet.py up <name>` starts it
again.  On a pod whose /workspace is the container disk (Runpod CPU pods have
no volume) a stop wipes the checkout, so uncommitted changes or unpushed
commits there also count as busy.  The current state is written to
/workspace/fleet/idle.json every minute.

cloud/modal_worker.py imports the probes below for its Modal workers, with
FLEET_WORKDIR pointing at their checkout.
"""
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FLEET = Path("/workspace/fleet")
WORKDIR = Path(os.environ.get("FLEET_WORKDIR", "/workspace/cryptanalysis"))
JOBS = Path("/workspace/jobs")
MANAGEMENT = os.environ.get("FLEET_MANAGEMENT_ADDR", "127.0.0.1:8787")
# Runpod's API sits behind Cloudflare, which refuses urllib's default User-Agent.
USER_AGENT = "cryptanalysis-fleet-idle/1"
BUSY_CORES = 0.25
BUSY_GPU_PERCENT = 5
EDIT_WINDOW_SECONDS = 600
PRUNE = {".git", "node_modules", "target", "__pycache__", ".venv"}
METRICS = {"cursor_self_hosted_worker_connected": "connected",
           "cursor_self_hosted_worker_session_active": "session_active",
           "cursor_self_hosted_worker_last_activity_unix_seconds": "last_activity"}


def log(message):
    print(f"[fleet idle {time.strftime('%H:%M:%S', time.gmtime())}] {message}", flush=True)


def read_config():
    config = {}
    for line in (FLEET / "config.env").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep:
            parsed = shlex.split(value)
            config[key] = parsed[0] if parsed else ""
    return config


def secret(name):
    try:
        return (FLEET / "secrets" / name).read_text().strip()
    except OSError:
        return ""


def parse_metrics(text):
    """The worker's connected / session_active / last_activity gauges."""
    out = {}
    for line in text.splitlines():
        name, _, value = line.rpartition(" ")
        if name in METRICS:
            try:
                out[METRICS[name]] = float(value)
            except ValueError:
                pass
    return out


def worker_metrics(address=MANAGEMENT):
    try:
        with urllib.request.urlopen(f"http://{address}/metrics", timeout=10) as response:
            return parse_metrics(response.read().decode(errors="replace"))
    except (OSError, ValueError):
        return {}


def agent_busy(metrics):
    # last_activity moves with the server's heartbeat frames every 30 s, so it
    # says nothing about agents; only an open session does.
    return "agent session" if metrics.get("session_active") else None


def cpu_seconds():
    """CPU time used by this container so far (its cgroup, not the host)."""
    try:
        for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines():
            if line.startswith("usage_usec "):
                return int(line.split()[1]) / 1e6
    except OSError:
        pass
    try:
        return int(Path("/sys/fs/cgroup/cpuacct/cpuacct.usage").read_text()) / 1e9
    except OSError:
        pass
    ticks = os.sysconf("SC_CLK_TCK")
    total = 0
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
            total += int(fields[11]) + int(fields[12])
        except (OSError, IndexError, ValueError):
            continue
    return total / ticks


def gpu_percent():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    values = [int(v) for v in out.split() if v.strip().isdigit()]
    return max(values) if values else None


def ssh_logged_in():
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if cmdline.read_bytes().startswith(b"sshd: root@"):
                return True
        except OSError:
            continue
    return False


def job_running():
    for pidfile in JOBS.glob("*/pid"):
        if (pidfile.parent / "status.json").exists():
            continue
        try:
            os.kill(int(pidfile.read_text().strip()), 0)
            return True
        except (OSError, ValueError):
            continue
    return False


def worktrees(root=None):
    root = Path(root or WORKDIR)
    roots = [root]
    try:
        out = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=30).stdout
        roots += [Path(line[9:]) for line in out.splitlines() if line.startswith("worktree ")]
    except (OSError, subprocess.SubprocessError):
        pass
    return {r for r in roots if r.is_dir()}


def recent_edit(root=None, since=0.0, limit=50000):
    """A file changed in the last EDIT_WINDOW_SECONDS, and after `since`.

    `since` excludes the checkout's own creation: a fresh clone stamps every
    file with the time it was written.
    """
    cutoff = max(time.time() - EDIT_WINDOW_SECONDS, since)
    seen = 0
    for tree in worktrees(root):
        for dirpath, dirnames, filenames in os.walk(tree):
            dirnames[:] = [d for d in dirnames if d not in PRUNE and not d.startswith("build")]
            for name in filenames:
                seen += 1
                if seen > limit:
                    return False
                try:
                    if os.lstat(os.path.join(dirpath, name)).st_mtime > cutoff:
                        return True
                except OSError:
                    continue
    return False


def volume_backed():
    """False when /workspace is the container disk, which a stop wipes (Runpod CPU pods)."""
    try:
        return os.stat("/workspace").st_dev != os.stat("/").st_dev
    except OSError:
        return False


def unsaved_work(root=None):
    """Uncommitted changes or unpushed commits in the agents' checkout or its worktrees."""
    for tree in worktrees(root):
        try:
            dirty = subprocess.run(["git", "-C", str(tree), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=60).stdout.strip()
            ahead = subprocess.run(["git", "-C", str(tree), "log", "--oneline", "-1",
                                    "--branches", "--not", "--remotes"],
                                   capture_output=True, text=True, timeout=60).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if dirty or ahead:
            return True
    return False


def stop_pod():
    # Runpod injects a key scoped to this pod; the GraphQL API accepts it, REST does not.
    key = secret("runpod-api-key")
    pod = secret("runpod-pod-id")
    if not key or not pod:
        log("cannot stop: no Runpod pod key or pod id on this pod")
        return False
    query = 'mutation { podStop(input: {podId: "%s"}) { id desiredStatus } }' % pod
    request = urllib.request.Request(
        "https://api.runpod.io/graphql", method="POST",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            reply = json.load(response)
    except (OSError, ValueError) as err:
        log(f"stop failed: {err}")
        return False
    if reply.get("errors"):
        log(f"stop failed: {reply['errors']}")
        return False
    log(f"stop requested: {reply.get('data')}")
    return True


def main():
    config = read_config()
    limit = int(config.get("FLEET_IDLE_STOP_MINUTES") or 0)
    if limit <= 0:
        log("idle stop disabled")
        return 0
    keep_unsaved = not volume_backed()
    log(f"stopping this pod after {limit} idle minutes"
        + (" (never while the checkout has unsaved work: a stop wipes /workspace here)"
           if keep_unsaved else ""))
    started = last_busy = time.time()
    before_cpu, before = cpu_seconds(), time.monotonic()
    while True:
        time.sleep(60)
        cpu, now = cpu_seconds(), time.monotonic()
        cores = max(0.0, (cpu - before_cpu) / max(1e-6, now - before))
        before_cpu, before = cpu, now
        gpu = gpu_percent()
        metrics = worker_metrics()
        reasons = [r for r in (agent_busy(metrics),) if r]
        if cores > BUSY_CORES:
            reasons.append(f"cpu {cores:.2f} cores")
        if gpu is not None and gpu > BUSY_GPU_PERCENT:
            reasons.append(f"gpu {gpu}%")
        if ssh_logged_in():
            reasons.append("ssh session")
        if job_running():
            reasons.append("fleet job")
        if not reasons and recent_edit(since=started):
            reasons.append("recent edits")
        if not reasons and keep_unsaved and unsaved_work():
            reasons.append("unsaved work in the checkout")
        if reasons:
            last_busy = time.time()
        idle = (time.time() - last_busy) / 60
        state = {"limit_minutes": limit, "idle_minutes": round(idle, 1), "busy": reasons,
                 "cores": round(cores, 3), "gpu_percent": gpu,
                 "worker": metrics or None,
                 "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (FLEET / "idle.json").write_text(json.dumps(state, indent=1) + "\n")
        if idle >= limit:
            log(f"idle for {idle:.0f} minutes; stopping the pod")
            if stop_pod():
                time.sleep(600)
            last_busy = time.time()


if __name__ == "__main__":
    sys.exit(main())
