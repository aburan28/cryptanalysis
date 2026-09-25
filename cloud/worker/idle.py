#!/usr/bin/env python3
"""Stop this pod after FLEET_IDLE_STOP_MINUTES without work.

boot.sh runs this in the tmux session `fleet-idle` when the limit is positive.
A minute counts as busy when any of these hold:

* the container's cgroup used more than BUSY_CORES of CPU,
* a GPU was more than BUSY_GPU_PERCENT utilized,
* someone is logged in over SSH,
* a `cloud/fleet.py run` job is still running,
* a file in the agents' checkout (or one of its worktrees) changed recently,
* Cursor reports this worker in use.

The pod is stopped, not terminated, and `cloud/fleet.py up <name>` starts it
again.  On a pod whose /workspace is the container disk (Runpod CPU pods have
no volume) a stop wipes the checkout, so uncommitted changes or unpushed
commits there also count as busy.  The current state is written to
/workspace/fleet/idle.json every minute.
"""
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

FLEET = Path("/workspace/fleet")
WORKDIR = Path("/workspace/cryptanalysis")
JOBS = Path("/workspace/jobs")
BUSY_CORES = 0.25
BUSY_GPU_PERCENT = 5
EDIT_WINDOW_SECONDS = 600
CURSOR_POLL_SECONDS = 300
PRUNE = {".git", "node_modules", "target", "__pycache__", ".venv"}


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


def worktrees():
    roots = [WORKDIR]
    try:
        out = subprocess.run(["git", "-C", str(WORKDIR), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=30).stdout
        roots += [Path(line[9:]) for line in out.splitlines() if line.startswith("worktree ")]
    except (OSError, subprocess.SubprocessError):
        pass
    return {r for r in roots if r.is_dir()}


def recent_edit(limit=50000):
    cutoff = time.time() - EDIT_WINDOW_SECONDS
    seen = 0
    for root in worktrees():
        for dirpath, dirnames, filenames in os.walk(root):
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


def cursor_in_use(key, name):
    if not key:
        return None
    request = urllib.request.Request(
        "https://api.cursor.com/v0/private-workers?scope=personal&limit=100",
        headers={"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            workers = json.load(response).get("workers", [])
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return any(w.get("name") == name and w.get("isInUse") for w in workers)


def volume_backed():
    """False when /workspace is the container disk, which a stop wipes (Runpod CPU pods)."""
    try:
        return os.stat("/workspace").st_dev != os.stat("/").st_dev
    except OSError:
        return False


def unsaved_work():
    """Uncommitted changes or unpushed commits in the agents' checkout or its worktrees."""
    for root in worktrees():
        try:
            dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=60).stdout.strip()
            ahead = subprocess.run(["git", "-C", str(root), "log", "--oneline", "-1",
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
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
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
    name = config.get("FLEET_WORKER_NAME", "")
    keep_unsaved = not volume_backed()
    log(f"stopping this pod after {limit} idle minutes"
        + (" (never while the checkout has unsaved work: a stop wipes /workspace here)"
           if keep_unsaved else ""))
    last_busy = time.time()
    in_use, in_use_checked = None, 0.0
    before_cpu, before = cpu_seconds(), time.monotonic()
    while True:
        time.sleep(60)
        cpu, now = cpu_seconds(), time.monotonic()
        cores = max(0.0, (cpu - before_cpu) / max(1e-6, now - before))
        before_cpu, before = cpu, now
        gpu = gpu_percent()
        if time.time() - in_use_checked >= CURSOR_POLL_SECONDS:
            in_use, in_use_checked = cursor_in_use(secret("cursor-api-key"), name), time.time()
        reasons = []
        if cores > BUSY_CORES:
            reasons.append(f"cpu {cores:.2f} cores")
        if gpu is not None and gpu > BUSY_GPU_PERCENT:
            reasons.append(f"gpu {gpu}%")
        if ssh_logged_in():
            reasons.append("ssh session")
        if job_running():
            reasons.append("fleet job")
        if in_use:
            reasons.append("cursor agent")
        if not reasons and recent_edit():
            reasons.append("recent edits")
        if not reasons and keep_unsaved and unsaved_work():
            reasons.append("unsaved work in the checkout")
        if reasons:
            last_busy = time.time()
        idle = (time.time() - last_busy) / 60
        state = {"limit_minutes": limit, "idle_minutes": round(idle, 1), "busy": reasons,
                 "cores": round(cores, 3), "gpu_percent": gpu, "cursor_in_use": in_use,
                 "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (FLEET / "idle.json").write_text(json.dumps(state, indent=1) + "\n")
        if idle >= limit:
            log(f"idle for {idle:.0f} minutes; stopping the pod")
            if stop_pod():
                time.sleep(600)
            last_busy = time.time()


if __name__ == "__main__":
    sys.exit(main())
