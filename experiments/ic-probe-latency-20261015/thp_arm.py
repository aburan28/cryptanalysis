#!/usr/bin/env python3
"""One IC or rho arm under a declared page policy (ic-probe-latency-20261015).

A thin wrapper around the reconciliation's frozen `arm.py`
(`experiments/koblitz-n83-reconcile-20261014/arm.py`), which it imports
unchanged. Only the producer's page policy differs between arms:

* `4k`:  the producer runs with PR_SET_THP_DISABLE (inherited across exec),
  so no transparent huge page backs any of its memory;
* `thp`: the producer runs with GLIBC_TUNABLES=glibc.malloc.hugetlb=1, so
  glibc calls madvise(MADV_HUGEPAGE) on every mmap'd chunk, including the
  root table's single 4 GiB `vec!` (K600: 2^27 slots x 32 bytes);
* `default`: neither; the runner's own THP mode decides, exactly as in the
  earlier n=83 GitHub runs (their allocation.json recorded enabled=always,
  defrag=madvise).

The binary, arguments, inputs and the producer's own online clock are
arm.py's. While the producer runs, the wrapper (moved off the execution CPU
after the fork) samples /proc/<pid>/smaps_rollup every 0.5 s and prints the
largest AnonHugePages and Rss it saw: the manipulation check.

    thp_arm.py --policy 4k|default|thp --off-cpu N <arm.py arguments ...>
"""
import argparse
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE.parent / "koblitz-n83-reconcile-20261014" / "arm.py"
PR_SET_THP_DISABLE = 41
THP_TUNABLE = "glibc.malloc.hugetlb=1"


def load_arm():
    spec = importlib.util.spec_from_file_location("reconcile_arm", ARM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smaps(pid):
    out = {}
    try:
        for line in Path("/proc/%d/smaps_rollup" % pid).read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in ("Rss", "AnonHugePages", "Private_Hugetlb", "Shared_Hugetlb"):
                out[key] = int(rest.split()[0])
    except (OSError, ValueError):
        pass
    return out


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--policy", required=True, choices=("4k", "default", "thp"))
    parser.add_argument("--off-cpu", type=int, required=True)
    ours, rest = parser.parse_known_args()
    arm = load_arm()
    libc = ctypes.CDLL(None, use_errno=True)
    seen = {"samples": 0, "max_anon_huge_kb": 0, "max_rss_kb": 0, "max_hugetlb_kb": 0,
            "policy": ours.policy, "prctl_rc": None}

    if ours.policy == "thp":
        arm.BASE_ENV["GLIBC_TUNABLES"] = THP_TUNABLE
    else:
        arm.BASE_ENV.pop("GLIBC_TUNABLES", None)

    def preexec():
        if ours.policy == "4k":
            if libc.prctl(PR_SET_THP_DISABLE, 1, 0, 0, 0) != 0:
                os._exit(97)

    def run(command, env):
        proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, preexec_fn=preexec)
        # The producer inherited the execution CPU; the sampler leaves it.
        os.sched_setaffinity(0, {ours.off_cpu})
        stop = threading.Event()

        def sample():
            while not stop.is_set():
                s = smaps(proc.pid)
                if s:
                    seen["samples"] += 1
                    seen["max_anon_huge_kb"] = max(seen["max_anon_huge_kb"], s.get("AnonHugePages", 0))
                    seen["max_rss_kb"] = max(seen["max_rss_kb"], s.get("Rss", 0))
                    seen["max_hugetlb_kb"] = max(seen["max_hugetlb_kb"],
                                                 s.get("Private_Hugetlb", 0) + s.get("Shared_Hugetlb", 0))
                stop.wait(0.5)

        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        stdout, stderr = proc.communicate()
        stop.set()
        thread.join()
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)

    arm.run = run
    sys.argv = [str(ARM)] + rest
    code = 0
    try:
        arm.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    seen["env_glibc_tunables"] = arm.BASE_ENV.get("GLIBC_TUNABLES")
    print("pages_json=" + json.dumps(seen, sort_keys=True, separators=(",", ":")))
    sys.stdout.flush()
    sys.exit(code)


if __name__ == "__main__":
    main()
