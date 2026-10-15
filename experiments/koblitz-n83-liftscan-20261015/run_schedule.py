#!/usr/bin/env python3
"""Execute the frozen schedule, one pinned process at a time, and keep every row.

Adapted from `../koblitz-n83-reconcile-20261014/run_schedule.py` (same
counters, noise gate, time guard and ledger); only the arm command line and
the timeouts differ.

Reads `protocol.json` and `schedule.json`, launches `arm.py` for every run in
order on one execution CPU (sched_setaffinity before exec, clean environment
from `scripts/isolated_bench.py`), and records per run: exit status, the arm's
fields, process wall, child CPU and peak RSS, and the Tier 1 counters and noise
gate of `isolated_bench` (cgroup cpu.stat throttling, memory events, steal on
the execution CPU, major faults) before and after. Rows are appended to
`runs.jsonl` and fsynced; stdout/stderr are kept per serial. Nothing is re-run.

Time guard (protocol `design.time_guard`): before each segment, if the elapsed
time since `--job-start-epoch` plus the segment's upper estimate exceeds
`--deadline-min`, that segment and all later ones are written as
`skipped_time_guard` rows and not run.

`--segments`, `--one-per-arm` and `--max-runs-per-segment` exist for the local smoke
test only (a correctness check, never timing evidence); the workflow passes none
of them.
"""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import isolated_bench as ib  # noqa: E402  (Tier 1 counters and noise gate)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fields_of(stdout):
    for line in reversed(stdout.splitlines()):
        if "online_ms=" in line and "verified=" in line:
            return dict(word.split("=", 1) for word in line.split() if "=" in word)
    return {}


def command(protocol, run, args, receipt_dir):
    arm = protocol["arms"][run["arm"]]
    argv = [str(args.python), str(HERE / "arm.py"), "--arm", run["arm"], "--kind", arm["kind"],
            "--panel", run["point_id"], "--binary", str(args.bin_dir / arm["binary"]),
            "--seed", str(run["seed"])]
    if run["point"] is not None:
        argv += ["--point", "%s,%s" % tuple(run["point"])]
    if arm["kind"] == "stage":
        argv += ["--mode", arm["mode"]]
    if arm["kind"] == "rho_tuned":
        argv += ["--config", str(HERE / protocol["online"]["tuned_rho_config"])]
    if arm["kind"] == "ic":
        argv += ["--canon", arm["canon"], "--base", str(HERE / protocol["online"]["base"]),
                 "--log-table", str(args.log_table)]
    return argv


def timeout_for(protocol, run):
    arm = protocol["arms"][run["arm"]]
    return protocol["design"]["timeout_s"][arm["kind"] + ("_verify" if run["arm"].endswith("V") else "")]


def one(protocol, run, args, receipt_dir, cgroup):
    argv = command(protocol, run, args, receipt_dir)
    binary = Path(argv[argv.index("--binary") + 1])
    binary_before = sha256(binary)
    cpus = {args.cpu}
    before = ib.counters(cpus, cgroup)
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic_ns()

    def child_setup():
        os.sched_setaffinity(0, {args.cpu})

    proc = subprocess.Popen(argv, cwd=str(HERE), env=ib.benchmark_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True, preexec_fn=child_setup)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_for(protocol, run))
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    wall_ms = (time.monotonic_ns() - started) / 1e6
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    after = ib.counters(cpus, cgroup)
    stdout, stderr = stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")
    stem = "%05d" % run["serial"]
    (receipt_dir / "runs" / (stem + ".stdout.txt")).write_text(stdout)
    (receipt_dir / "runs" / (stem + ".stderr.txt")).write_text(stderr)
    fields = fields_of(stdout)
    noise = ib.noise(before, after, usage_before, usage_after, "tier1")
    memory_events = [item for item in noise if item.startswith("memory event")]
    contention = [item for item in noise if item not in memory_events]
    issues = []
    if proc.returncode != 0:
        issues.append("nonzero exit %d" % proc.returncode)
    if timed_out:
        issues.append("timeout")
    if fields.get("verified") != "1":
        issues.append("missing verified=1")
    if sha256(binary) != binary_before:
        issues.append("binary changed during the run")
    issues += memory_events
    try:
        online = float(fields.get("online_ms", "nan"))
        if not online > 0 or online > wall_ms:
            issues.append("online_ms missing, nonpositive or above process wall")
    except ValueError:
        issues.append("online_ms unparsable")
    return {
        "serial": run["serial"], "arm": run["arm"], "point_id": run["point_id"], "seed": run["seed"],
        "rank_seed": run.get("rank_seed"), "status": "valid" if not issues else "invalid",
        "issues": issues, "contention_flags": contention, "command": argv,
        "binary_sha256": binary_before, "returncode": proc.returncode, "timed_out": timed_out,
        "process_wall_ms": wall_ms,
        "child_cpu_user_ms": (usage_after.ru_utime - usage_before.ru_utime) * 1000,
        "child_cpu_system_ms": (usage_after.ru_stime - usage_before.ru_stime) * 1000,
        "child_peak_rss_kb_cumulative": usage_after.ru_maxrss,
        "child_involuntary_switches": usage_after.ru_nivcsw - usage_before.ru_nivcsw,
        "child_major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
        "fields": fields, "counters_before": before, "counters_after": after,
        "stdout_file": "runs/" + stem + ".stdout.txt", "stderr_file": "runs/" + stem + ".stderr.txt",
        "finished_unix_s": time.time(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", required=True, type=Path)
    parser.add_argument("--log-table", required=True, type=Path)
    parser.add_argument("--receipt-dir", required=True, type=Path)
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--job-start-epoch", type=float, default=time.time())
    parser.add_argument("--deadline-min", type=float, default=325.0)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--segments", help="smoke only: comma-separated segment ids")
    parser.add_argument("--one-per-arm", action="store_true", help="smoke only: first run of each arm")
    parser.add_argument("--max-runs-per-segment", type=int, help="smoke only: first k runs of each segment")
    args = parser.parse_args()
    args.bin_dir = args.bin_dir.resolve(strict=True)
    args.log_table = args.log_table.resolve(strict=True)
    protocol = json.loads((HERE / "protocol.json").read_text())
    schedule = json.loads((HERE / "schedule.json").read_text())
    if sha256(args.log_table) != protocol["online"]["factor_log_table_sha256"]:
        raise SystemExit("factor-log table differs from the protocol's")
    receipt_dir = args.receipt_dir.resolve()
    (receipt_dir / "runs").mkdir(parents=True, exist_ok=False)
    cgroup = ib.current_cgroup()
    estimates = protocol["design"]["segment_upper_estimate_s"]
    binaries = sorted({arm["binary"] for arm in protocol["arms"].values()})
    start = {"job_start_epoch": args.job_start_epoch, "runner_started_epoch": time.time(),
             "execution_cpu": args.cpu, "cgroup": str(cgroup), "host": ib.host_probe(),
             "protocol_sha256": sha256(HERE / "protocol.json"),
             "schedule_sha256": sha256(HERE / "schedule.json"),
             "arm_wrapper_sha256": sha256(HERE / "arm.py"), "runner_sha256": sha256(Path(__file__)),
             "isolated_bench_sha256": sha256(REPO / "scripts/isolated_bench.py"),
             "log_table_sha256": sha256(args.log_table),
             "binaries_sha256": {name: sha256(args.bin_dir / name) for name in binaries},
             "smoke_subset": {"segments": args.segments, "one_per_arm": args.one_per_arm,
                              "max_runs_per_segment": args.max_runs_per_segment}}
    (receipt_dir / "runner_start.json").write_text(json.dumps(start, indent=2, sort_keys=True) + "\n")
    wanted = set(args.segments.split(",")) if args.segments else None
    guard_tripped = False
    observed = {}
    counts = {"valid": 0, "invalid": 0, "skipped_time_guard": 0}
    with (receipt_dir / "runs.jsonl").open("w") as ledger:
        def write(row):
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            counts[row["status"]] = counts.get(row["status"], 0) + 1

        for segment in schedule["segments"]:
            if wanted is not None and segment["id"] not in wanted:
                continue
            elapsed = time.time() - args.job_start_epoch
            # The guard uses the larger of the frozen upper estimate and 1.1x the
            # longest segment of the same panel observed so far in this job.
            projected = max(estimates[segment["panel"]], 1.1 * observed.get(segment["panel"], 0.0))
            if guard_tripped or elapsed + projected > args.deadline_min * 60:
                guard_tripped = True
                for run in segment["runs"]:
                    write({"serial": run["serial"], "arm": run["arm"], "point_id": run["point_id"],
                           "seed": run["seed"], "segment": segment["id"], "status": "skipped_time_guard",
                           "elapsed_s_at_guard": elapsed})
                continue
            runs = segment["runs"]
            if args.one_per_arm:
                firsts = {}
                for run in runs:
                    firsts.setdefault(run["arm"], run)
                runs = sorted(firsts.values(), key=lambda run: run["serial"])
            if args.max_runs_per_segment:
                runs = runs[:args.max_runs_per_segment]
            segment_started = time.time()
            for run in runs:
                row = one(protocol, run, args, receipt_dir, cgroup)
                row["segment"] = segment["id"]
                write(row)
                print(json.dumps({"serial": row["serial"], "arm": row["arm"], "point": row["point_id"],
                                  "status": row["status"], "issues": row["issues"]}), flush=True)
            observed[segment["panel"]] = max(observed.get(segment["panel"], 0.0), time.time() - segment_started)
    end = {"finished_epoch": time.time(), "counts": counts, "guard_tripped": guard_tripped,
           "binaries_sha256_after": {name: sha256(args.bin_dir / name) for name in binaries}}
    (receipt_dir / "runner_end.json").write_text(json.dumps(end, indent=2, sort_keys=True) + "\n")
    print(json.dumps(end, sort_keys=True))


if __name__ == "__main__":
    main()
