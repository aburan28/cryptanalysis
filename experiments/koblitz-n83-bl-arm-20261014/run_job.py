#!/usr/bin/env python3
"""Run the frozen n=83 panel, one pinned process at a time, and keep every row.

The schedule is derived from protocol.json (`schedule()` below, printed by
`--print-schedule`): targets in the order Q0 block 0, w00-w03, Q0 block 1,
w04-w07, Q0 block 2, w08-w11, Q0 block 3, w12-w15, then the step-identity
control; at the k-th target the four arms run in rotation k mod 4 of
[ic, bl, rho, bl_aa]. Every run goes through `arm.py` on one execution CPU
(sched_setaffinity before exec, clean environment from
`scripts/isolated_bench.py`), and records exit status, the arm's fields,
process wall, child CPU and RSS, and isolated_bench's Tier 1 counters and noise
flags before and after. Rows are appended to `runs.jsonl` and fsynced;
stdout/stderr are kept per serial. Nothing is re-run.

Time guard: before each target, if the elapsed time since `--job-start-epoch`
plus 1.1 times the longest target so far (at least the frozen upper estimate)
exceeds `--deadline-min`, that target and all later ones are written as
`skipped_time_guard` rows.
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

ROTATION = ["ic", "bl", "rho", "bl_aa"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def schedule(protocol, targets):
    q0 = targets["q0"]["point"]
    points = {entry["seed"]: entry["point"] for entry in targets["panel_b"]["points"]}
    panel = protocol["panels"]
    order = []
    for block in range(panel["Q"]["blocks"]):
        order.append(("q0", q0, panel["Q"]["seeds"][block], "Q", block))
        for w in range(block * 4, block * 4 + 4):
            order.append(("w%02d" % w, points[w], panel["F"]["seed_base"] + w, "F", None))
    runs = []
    serial = 0
    for k, (point_id, point, seed, panel_id, block) in enumerate(order):
        arms = ROTATION[k % 4:] + ROTATION[:k % 4]
        for arm in arms:
            runs.append({"serial": serial, "target_index": k, "point_id": point_id, "point": point,
                         "seed": seed, "panel": panel_id, "block": block, "arm": arm})
            serial += 1
    control = protocol["controls"]["step_identity"]
    runs.append({"serial": serial, "target_index": len(order), "point_id": "q0", "point": q0,
                 "seed": control["seed"], "panel": "S", "block": None, "arm": "bl_plain"})
    return runs


def command(protocol, impl, run, args):
    spec = protocol["rho_step_implementations"][impl]
    bl = protocol["bl"]
    point = "%s,%s" % tuple(run["point"])
    base = [str(args.python), str(HERE / "arm.py"), "--arm", run["arm"], "--panel", run["point_id"],
            "--point", point, "--seed", str(run["seed"])]
    if run["arm"] == "ic":
        return base + ["--kind", "ic_online_cached", "--binary", str(args.bin_dir / protocol["ic"]["binary"]),
                       "--base", str(HERE / "snapshot" / protocol["inputs"]["base"]),
                       "--base-hash", protocol["inputs"]["base_hash"], "--log-table", str(args.log_table),
                       "--rank-seed", str(protocol["precompute"]["rank_seed"]),
                       "--columns", str(protocol["inputs"]["orbit_columns"])]
    if run["arm"] == "rho":
        ref = spec["reference"]
        argv = base + ["--kind", ref["kind"], "--binary", str(args.bin_dir / ref["binary"])]
        if ref.get("config"):
            argv += ["--config", str(HERE / "snapshot" / ref["config"])]
        return argv
    b = spec["bl"]
    kind = b["plain_kind"] if run["arm"] == "bl_plain" else b["kind"]
    argv = base + ["--kind", kind, "--binary", str(args.bin_dir / b["binary"]), "--lanes", str(b["lanes"]),
                   "--reference-dp-bits", str(spec["reference"]["dp_bits"])]
    if b.get("field"):
        argv += ["--field", b["field"]]
    if run["arm"] != "bl_plain":
        argv += ["--dp-bits", str(bl["dp_bits"]), "--bl-jump-seed", str(bl["bl_jump_seed"]),
                 "--table", str(args.table), "--table-blake3", args.table_blake3,
                 "--table-entries", str(args.table_entries)]
    return argv


def fields_of(stdout):
    for line in reversed(stdout.splitlines()):
        if "online_ms=" in line and "verified=" in line:
            return dict(word.split("=", 1) for word in line.split() if "=" in word)
    return {}


def one(protocol, impl, run, args, receipt_dir, cgroup):
    argv = command(protocol, impl, run, args)
    binary = Path(argv[argv.index("--binary") + 1])
    binary_before = sha256(binary)
    cpus = {args.cpu}
    before = ib.counters(cpus, cgroup)
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic_ns()
    proc = subprocess.Popen(argv, cwd=str(HERE), env=ib.benchmark_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True,
                            preexec_fn=lambda: os.sched_setaffinity(0, {args.cpu}))
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=protocol["panels"]["timeout_s"][run["arm"]])
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
    row = {key: run[key] for key in ("serial", "target_index", "point_id", "seed", "panel", "block", "arm")}
    row.update({"implementation": impl, "status": "valid" if not issues else "invalid", "issues": issues,
                "contention_flags": contention, "command": argv, "binary_sha256": binary_before,
                "returncode": proc.returncode, "timed_out": timed_out, "process_wall_ms": wall_ms,
                "child_cpu_user_ms": (usage_after.ru_utime - usage_before.ru_utime) * 1000,
                "child_cpu_system_ms": (usage_after.ru_stime - usage_before.ru_stime) * 1000,
                "child_peak_rss_kb_cumulative": usage_after.ru_maxrss,
                "child_involuntary_switches": usage_after.ru_nivcsw - usage_before.ru_nivcsw,
                "child_major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
                "fields": fields, "counters_before": before, "counters_after": after,
                "stdout_file": "runs/" + stem + ".stdout.txt", "stderr_file": "runs/" + stem + ".stderr.txt",
                "finished_unix_s": time.time()})
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument("--log-table", type=Path)
    parser.add_argument("--bl-receipt-dir", type=Path, help="bl_table.py output (table.bin, receipts)")
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--job-start-epoch", type=float, default=time.time())
    parser.add_argument("--deadline-min", type=float, default=330.0)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--print-schedule", action="store_true")
    parser.add_argument("--targets-limit", type=int, help="smoke only: the first k targets of the order")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    targets_path = HERE / protocol["inputs"]["targets_file"]
    if sha256(targets_path) != protocol["inputs"]["targets_sha256"]:
        raise SystemExit("targets file differs from the protocol")
    targets = json.loads(targets_path.read_text())
    runs = schedule(protocol, targets)
    if args.print_schedule:
        for run in runs:
            print(json.dumps({k: v for k, v in run.items() if k != "point"}, sort_keys=True))
        return
    bl_receipt = json.loads((args.bl_receipt_dir / "precompute_receipt.json").read_text())
    checks = json.loads((args.bl_receipt_dir / "table_checks.json").read_text())
    if bl_receipt["status"] != "PASS" or checks["status"] != "PASS":
        raise SystemExit("the BL table did not pass its checks; no online arm runs")
    impl = bl_receipt["implementation"]
    if not bl_receipt["implementation_overridden_for_smoke"] and impl != protocol["rho_reference"]["value"]:
        raise SystemExit("the table was built for another implementation")
    args.table = (args.bl_receipt_dir / "table.bin").resolve(strict=True)
    args.table_blake3 = bl_receipt["producer"]["table_blake3"]
    args.table_entries = bl_receipt["producer"]["table_entries"]
    if sha256(args.table) != bl_receipt["table_sha256"]:
        raise SystemExit("table.bin differs from its receipt")
    args.bin_dir = args.bin_dir.resolve(strict=True)
    args.log_table = args.log_table.resolve(strict=True)
    if sha256(args.log_table) != protocol["inputs"]["factor_log_table_archived_sha256"]:
        raise SystemExit("factor-log table differs from B's archived table")
    receipt_dir = args.receipt_dir.resolve()
    (receipt_dir / "runs").mkdir(parents=True, exist_ok=False)
    cgroup = ib.current_cgroup()
    binaries = sorted({Path(command(protocol, impl, run, args)[command(protocol, impl, run, args).index("--binary") + 1]).name
                       for run in runs})
    start = {"job_start_epoch": args.job_start_epoch, "runner_started_epoch": time.time(),
             "execution_cpu": args.cpu, "cgroup": str(cgroup), "host": ib.host_probe(),
             "implementation": impl, "implementation_overridden_for_smoke": bl_receipt["implementation_overridden_for_smoke"],
             "protocol_sha256": sha256(HERE / "protocol.json"), "arm_wrapper_sha256": sha256(HERE / "arm.py"),
             "runner_sha256": sha256(Path(__file__)), "isolated_bench_sha256": sha256(REPO / "scripts/isolated_bench.py"),
             "log_table_sha256": sha256(args.log_table), "bl_table_sha256": bl_receipt["table_sha256"],
             "binaries_sha256": {name: sha256(args.bin_dir / name) for name in binaries},
             "targets_limit": args.targets_limit, "schedule_runs": len(runs)}
    (receipt_dir / "runner_start.json").write_text(json.dumps(start, indent=2, sort_keys=True) + "\n")
    estimate_s = protocol["resources"]["estimate_s"]["target_upper"]
    counts = {"valid": 0, "invalid": 0, "skipped_time_guard": 0, "skipped_smoke_limit": 0}
    longest = 0.0
    guard = False
    with (receipt_dir / "runs.jsonl").open("w") as ledger:
        def write(row):
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            counts[row["status"]] = counts.get(row["status"], 0) + 1

        by_target = {}
        for run in runs:
            by_target.setdefault(run["target_index"], []).append(run)
        for k in sorted(by_target):
            elapsed = time.time() - args.job_start_epoch
            limited = args.targets_limit is not None and k >= args.targets_limit and by_target[k][0]["panel"] != "S"
            if not guard and not limited and elapsed + max(estimate_s, 1.1 * longest) > args.deadline_min * 60:
                guard = True
            if guard or limited:
                for run in by_target[k]:
                    write({key: run[key] for key in ("serial", "target_index", "point_id", "seed", "panel", "block", "arm")} |
                          {"status": "skipped_time_guard" if guard else "skipped_smoke_limit", "elapsed_s": elapsed})
                continue
            target_started = time.time()
            for run in by_target[k]:
                row = one(protocol, impl, run, args, receipt_dir, cgroup)
                write(row)
                print(json.dumps({"serial": row["serial"], "arm": row["arm"], "point": row["point_id"],
                                  "status": row["status"], "issues": row["issues"],
                                  "online_ms": row["fields"].get("online_ms")}), flush=True)
            longest = max(longest, time.time() - target_started)
    end = {"finished_epoch": time.time(), "counts": counts, "guard_tripped": guard,
           "binaries_sha256_after": {name: sha256(args.bin_dir / name) for name in binaries}}
    (receipt_dir / "runner_end.json").write_text(json.dumps(end, indent=2, sort_keys=True) + "\n")
    print(json.dumps(end, sort_keys=True))


if __name__ == "__main__":
    main()
