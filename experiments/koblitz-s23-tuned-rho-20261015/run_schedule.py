#!/usr/bin/env python3
"""Run the frozen schedule: section 23's round with two external strong-rho arms.

One process at a time on one execution CPU (sched_setaffinity before exec,
the clean environment of `scripts/isolated_bench.py` plus RAYON_NUM_THREADS=1).
For every size (section 23's order of r) and target T01..T64 (run R1), then
T01..T04 again (run R2, the A/A), four arms run on the same public point:

* `ic`: crypto's `ic price --single-target` at baseline v3, on section 23's
  parameter file, with section 23's rho seed 0x230000 + i. One process holds
  the index calculus and the matched in-process ParallelRho, three
  repetitions each, exactly as section 23 and rule v3 ran it.
* `strong`: the default StrongRhoG parameters (32 lanes, DP 4, escape off) on
  the same field kernel as `tuned` (the one-word Gf2 at n <= 64), through the
  derived worker, walk seed 0x230000 + i.
* `strong_wide`: rA770's exact configuration (WideGf2, 32 lanes, DP 4), the
  same walk on the two-word field kernel.
* `tuned`: rT770's configuration (fold, 64 lanes, DP 6) through the same
  worker, walk seed 0x230000 + i.

The arms' order rotates with the target (`ARMS` rotated by (i - 1) mod 4 for
R1, by i mod 4 for R2). A run that fails, or that the Tier 1 noise gate flags
as contended, is kept and run again, up to twice (section 23's rule); the
first clean, valid attempt is the row. Nothing is overwritten.

Before the panel, the controls run on n = 83's Q0 (protocol `controls`):
the identity control (the worker must take rT770's and rA770's exact step
counts) and the positive control (the instrument must resolve the known
step-count ratio between two seeds).

Time guard: before each target block, if the elapsed time since
`--job-start-epoch` plus 1.5x the slowest block seen at that size (60 s before
the first) exceeds `--deadline-min`, every remaining block is written as
`skipped_time_guard` and not run.

`--sizes`, `--targets` and `--aa` exist for the local smoke test only (a
correctness check, never timing evidence); the workflow passes none of them.
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import isolated_bench as ib  # noqa: E402  (Tier 1 counters and noise gate)

PROTOCOL = json.loads((HERE / "protocol.json").read_text())
TARGETS = json.loads((HERE / "inputs" / "targets.json").read_text())
ARMS = ["ic", "strong", "strong_wide", "tuned"]
SIZES = [(1, 47), (0, 57), (0, 41), (0, 53), (1, 59), (0, 61)]
RHO_SEED_BASE = 0x230000
S23_PARAMS = "research/ic_single_target_20260930/runs"
TUNED_CONFIG = HERE / "snapshots/r770/research/n83_evaluation_20261012/optimization/selected_config.json"
CONFIGS = {"strong": HERE / "configs" / "default_strong.json",
           "strong_wide": HERE / "configs" / "default_strong_wide.json",
           "tuned": TUNED_CONFIG}
RETRIES = 2


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append(path, row):
    with Path(path).open("a") as out:
        out.write(json.dumps(row, sort_keys=True) + "\n")
        out.flush()
        os.fsync(out.fileno())


def launch(argv, cpu, timeout_s, stdout_path, stderr_path, cgroup):
    """One pinned process; returns the run record (exit, wall, rusage, Tier 1 noise)."""
    binary = Path(argv[0])
    binary_before = sha256(binary)
    before = ib.counters({cpu}, cgroup)
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    env = ib.benchmark_env()
    env["RAYON_NUM_THREADS"] = "1"
    started = time.monotonic_ns()
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        proc = subprocess.Popen(argv, cwd=str(HERE), env=env, stdout=out, stderr=err,
                                start_new_session=True,
                                preexec_fn=lambda: os.sched_setaffinity(0, {cpu}))
        timed_out = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    wall_ms = (time.monotonic_ns() - started) / 1e6
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    after = ib.counters({cpu}, cgroup)
    noise = ib.noise(before, after, usage_before, usage_after, "tier1")
    memory_events = [item for item in noise if item.startswith("memory event")]
    contention = [item for item in noise if item not in memory_events]
    return {
        "exit_status": proc.returncode, "timed_out": timed_out, "process_wall_ms": wall_ms,
        "child_cpu_user_ms": (usage_after.ru_utime - usage_before.ru_utime) * 1000,
        "child_cpu_system_ms": (usage_after.ru_stime - usage_before.ru_stime) * 1000,
        "child_peak_rss_kb_cumulative": usage_after.ru_maxrss,
        "child_involuntary_switches": usage_after.ru_nivcsw - usage_before.ru_nivcsw,
        "child_major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
        "memory_events": memory_events, "contention_flags": contention,
        "contended": bool(contention), "binary_sha256": binary_before,
        "binary_changed": sha256(binary) != binary_before,
        "counters_before": before, "counters_after": after, "cpu": cpu,
    }


def rho_argv(args, arm, a, n, point_file, seed, receipt):
    config = CONFIGS[arm]
    return [str(args.rho), str(a), str(n), str(point_file), str(seed), str(config), str(receipt)]


def valid_ic(path):
    try:
        rep = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False, None
    return rep.get("status") == "complete" and rep.get("all_verified") is True, rep


def valid_rho(path):
    try:
        rep = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False, None
    return rep.get("status") == "PASS_VERIFIED_PUBLIC_TARGET", rep


def run_arm(args, arm, a, n, i, run, target, cgroup, log):
    """All attempts of one (arm, target, run); returns the attempts' rows."""
    size = f"k{a}n{n}"
    rows = []
    for k in range(RETRIES + 1):
        stem = f"T{i:02d}-R{run}" + (f"-retry{k}" if k else "")
        if arm == "ic":
            folder = args.receipt_dir / "runs" / size
            out = folder / (stem + ".price.json")
            argv = [str(args.ic), "price", "--params", str(folder / f"T{i:02d}.params.json"), "--json",
                    "--out", str(out), "--single-target", "--rho-seed", str(RHO_SEED_BASE + i)]
            timeout_s = PROTOCOL["timeouts_s"]["ic"]
        else:
            folder = args.receipt_dir / "rho" / arm / size
            out = folder / (stem + ".json")
            point_file = args.receipt_dir / "points" / size / f"T{i:02d}.jsonl"
            argv = rho_argv(args, arm, a, n, point_file, RHO_SEED_BASE + i, out)
            timeout_s = PROTOCOL["timeouts_s"]["rho"]
        folder.mkdir(parents=True, exist_ok=True)
        rec = launch(argv, args.cpu, timeout_s, folder / (stem + ".stdout"), folder / (stem + ".stderr"), cgroup)
        ok, rep = (valid_ic if arm == "ic" else valid_rho)(out)
        issues = []
        if rec["exit_status"] != 0:
            issues.append("nonzero exit %s" % rec["exit_status"])
        if rec["timed_out"]:
            issues.append("timeout")
        if rec["binary_changed"]:
            issues.append("binary changed during the run")
        issues += rec["memory_events"]
        if not ok:
            issues.append("report missing, incomplete or unverified")
        if ok and arm == "ic" and rep["certificates"]["ic"]["target"] != target["point"]:
            issues.append("IC target differs from the frozen public point")
        status = "valid" if not issues else "invalid"
        # claims.py reads the last line's "run" record of this file.
        (folder / (stem + ".isolation.jsonl")).write_text(json.dumps({"run": {
            "exit_status": rec["exit_status"], "contended": rec["contended"], "status": status,
            "issues": issues, "contention_flags": rec["contention_flags"], "cpu": args.cpu,
            "process_wall_ms": rec["process_wall_ms"]}}, sort_keys=True) + "\n")
        row = {"arm": arm, "size": size, "a": a, "n": n, "target": f"T{i:02d}", "run": run,
               "attempt": k, "file": str(out.relative_to(args.receipt_dir)), "command": argv,
               "status": status, "issues": issues, "finished_unix_s": time.time(), **rec}
        append(log, row)
        rows.append(row)
        if status == "valid" and not rec["contended"]:
            break
    return rows


def controls(args, cgroup, log):
    """Identity and positive controls on n = 83's Q0, before the panel."""
    q0 = PROTOCOL["controls"]["q0"]
    folder = args.receipt_dir / "controls"
    folder.mkdir(parents=True, exist_ok=True)
    point = folder / "q0.jsonl"
    point.write_text(json.dumps(q0["point"]) + "\n")
    out = []
    for case in PROTOCOL["controls"]["cases"]:
        receipt = folder / (case["id"] + ".json")
        argv = rho_argv(args, case["arm"], 1, 83, point, case["seed"], receipt)
        rec = launch(argv, args.cpu, PROTOCOL["timeouts_s"]["control"], folder / (case["id"] + ".stdout"),
                     folder / (case["id"] + ".stderr"), cgroup)
        ok, rep = valid_rho(receipt)
        row = {"control": case["id"], "arm": case["arm"], "seed": case["seed"], "valid": ok,
               "walk_steps": rep["outcome"]["walk_steps"] if ok else None,
               "online_ms": rep["online_ms"] if ok else None,
               "recovered_scalar": rep["recovered_scalar"] if ok else None, **rec}
        append(log, row)
        out.append(row)
    return out


def host_manifest(args):
    cpu_model = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                      if line.startswith("model name")), platform.processor())
    return {
        "what": "the host of this run, for section 23's claims.py (it reads these keys)",
        "commit": PROTOCOL["sources"]["v3_commit"], "ic_built_from": PROTOCOL["sources"]["v3_commit"],
        "ic_binary_sha256": sha256(args.ic), "rho_binary_sha256": sha256(args.rho),
        "cpu_model": cpu_model, "logical_cores": os.cpu_count(),
        "os": "%s %s" % (platform.system(), platform.release()), "execution_cpu": args.cpu,
        "python": platform.python_version(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ic", type=Path, required=True)
    parser.add_argument("--rho", type=Path, required=True)
    parser.add_argument("--crypto-repo", type=Path, required=True, help="the harness checkout (restore_sources.py)")
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--job-start-epoch", type=float, default=None)
    parser.add_argument("--deadline-min", type=float, default=PROTOCOL["time_guard"]["deadline_min"])
    parser.add_argument("--sizes", default=None, help="smoke only: comma list like k0n41")
    parser.add_argument("--targets", type=int, default=64, help="smoke only")
    parser.add_argument("--aa", type=int, default=4, help="smoke only")
    parser.add_argument("--skip-controls", action="store_true", help="smoke only")
    args = parser.parse_args()
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    args.ic, args.rho = args.ic.resolve(), args.rho.resolve()
    start = args.job_start_epoch or time.time()
    cgroup = ib.current_cgroup()
    log = args.receipt_dir / "runs.jsonl"
    (args.receipt_dir / "runs").mkdir(exist_ok=True)
    (args.receipt_dir / "runs" / "host.json").write_text(json.dumps(host_manifest(args), indent=1) + "\n")
    append(log, {"event": "start", "unix_s": time.time(), "smoke": bool(args.sizes or args.targets != 64 or args.aa != 4),
                 "protocol_sha256": sha256(HERE / "protocol.json")})
    if not args.skip_controls:
        controls(args, cgroup, log)
    by_key = {(t["a"], t["n"], t["target"]): t for t in TARGETS["targets"]}
    sizes = [s for s in SIZES if args.sizes is None or f"k{s[0]}n{s[1]}" in args.sizes.split(",")]
    plan = []
    for a, n in sizes:
        plan += [(a, n, i, 1) for i in range(1, args.targets + 1)]
        plan += [(a, n, i, 2) for i in range(1, args.aa + 1)]
    slowest = {}
    stopped = False
    for a, n, i, run in plan:
        size = f"k{a}n{n}"
        target = by_key[(a, n, f"T{i:02d}")]
        estimate = 1.5 * slowest.get(size, 60.0)
        if stopped or (time.time() - start + estimate) / 60.0 > args.deadline_min:
            stopped = True
            append(log, {"arm": "all", "size": size, "target": f"T{i:02d}", "run": run,
                         "status": "skipped_time_guard", "finished_unix_s": time.time()})
            continue
        params_src = args.crypto_repo / S23_PARAMS / size / f"T{i:02d}.params.json"
        params_dst = args.receipt_dir / "runs" / size / f"T{i:02d}.params.json"
        params_dst.parent.mkdir(parents=True, exist_ok=True)
        if not params_dst.exists():
            shutil.copyfile(params_src, params_dst)
        point_file = args.receipt_dir / "points" / size / f"T{i:02d}.jsonl"
        point_file.parent.mkdir(parents=True, exist_ok=True)
        point_file.write_text(json.dumps(target["point"]) + "\n")
        k = (i - 1) % 4 if run == 1 else i % 4
        began = time.time()
        for arm in ARMS[k:] + ARMS[:k]:
            run_arm(args, arm, a, n, i, run, target, cgroup, log)
        slowest[size] = max(slowest.get(size, 0.0), time.time() - began)
        print(json.dumps({"size": size, "target": i, "run": run, "block_s": round(time.time() - began, 2)}),
              flush=True)
    append(log, {"event": "end", "unix_s": time.time(), "stopped_by_time_guard": stopped})


if __name__ == "__main__":
    main()
