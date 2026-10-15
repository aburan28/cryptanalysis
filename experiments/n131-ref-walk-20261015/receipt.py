#!/usr/bin/env python3
"""Host snapshot for the Tier 1 receipt (taken before and after the timed run).

usage: python3 receipt.py <out.json>

Records what a GitHub-hosted job can see of its allocation: runner and image
identity, the Azure instance metadata if the endpoint answers, CPU model and
topology, kernel, affinity, cgroup CPU quota and throttling, steal and other
/proc/stat CPU time, load, memory.  Nothing here proves host-wide exclusivity;
the receipt says so.
"""
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request


def read(path):
    try:
        return open(path).read()
    except OSError as e:
        return f"unavailable: {e}"


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except Exception as e:  # noqa: BLE001
        return f"unavailable: {e}"


def imds():
    req = urllib.request.Request("http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                                 headers={"Metadata": "true"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read())
        c = d.get("compute", {})
        keep = ["vmId", "vmSize", "location", "zone", "osType", "sku", "version", "azEnvironment"]
        return {k: c.get(k) for k in keep}
    except Exception as e:  # noqa: BLE001
        return f"unavailable: {e}"


def proc_stat():
    out = {}
    for line in read("/proc/stat").splitlines():
        if line.startswith("cpu"):
            f = line.split()
            names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"]
            out[f[0]] = dict(zip(names, map(int, f[1:])))
        elif line.split()[:1] in (["ctxt"], ["intr"]):
            out[line.split()[0]] = int(line.split()[1])
    return out


def main():
    env_keys = ["RUNNER_NAME", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "ImageOS", "ImageVersion",
                "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF", "GITHUB_WORKFLOW"]
    snap = {
        "time_unix": time.time(),
        "provider": "GitHub-hosted runner (Azure VM); instance scoped, Tier 1 per AGENTS.md",
        "exclusivity": "not proven: a container/VM affinity mask records placement only",
        "env": {k: os.environ.get(k) for k in env_keys},
        "azure_imds": imds(),
        "uname": platform.uname()._asdict(),
        "nproc": os.cpu_count(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "lscpu": run(["lscpu"]),
        "cpu_model": next((l.split(":", 1)[1].strip() for l in read("/proc/cpuinfo").splitlines()
                           if l.startswith("model name")), None),
        "cpu_mhz": [l.split(":", 1)[1].strip() for l in read("/proc/cpuinfo").splitlines() if l.startswith("cpu MHz")],
        "cgroup_cpu_max": read("/sys/fs/cgroup/cpu.max").strip(),
        "cgroup_cpu_stat": read("/sys/fs/cgroup/cpu.stat"),
        "cgroup_memory_events": read("/sys/fs/cgroup/memory.events"),
        "proc_stat": proc_stat(),
        "loadavg": read("/proc/loadavg").strip(),
        "meminfo_head": "\n".join(read("/proc/meminfo").splitlines()[:5]),
        "scaling_governor": read("/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor").strip(),
        "clocksource": read("/sys/devices/system/clocksource/clocksource0/current_clocksource").strip(),
    }
    with open(sys.argv[1], "w") as f:
        json.dump(snap, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
