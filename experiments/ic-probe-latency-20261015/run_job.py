#!/usr/bin/env python3
"""The frozen schedule of ic-probe-latency-20261015 (protocol.json).

Every process runs alone, pinned to the execution CPU, in the order below;
isolated_bench's Tier 1 counters (cgroup throttling, memory events, steal,
interrupts) are recorded around each one.

  P1  pointer-chase sweep, 4k and thp, sizes x 2 rounds (mode order reversed
      in round 2);
  P2  pointer-chase with MAP_HUGETLB, only if the workflow reserved pages
      (not interleaved: the reservation takes the memory the others need);
  P3  IC panel on Q0: blocks k = 0..3, each running the three policies in
      protocol.json's block_orders[k]; after each IC process, a pointer
      chase over the root table's byte size under the same policy (the
      interleaved null, run after the 4k and thp processes only);
  P4  tuned-rho panel on Q0, same block orders (the compute control).

    run_job.py --bin-dir DIR --pchase BIN --log-table FILE --receipt-dir DIR \
        --cpu N --off-cpu M [--hugetlb-pages K] [--smoke]
"""
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RECONCILE = HERE.parent / "koblitz-n83-reconcile-20261014"
sys.path.insert(0, str(REPO / "scripts"))
import isolated_bench as ib  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def meminfo():
    out = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, _, v = line.partition(":")
        if k in ("MemTotal", "MemAvailable", "AnonHugePages", "HugePages_Total", "HugePages_Free"):
            out[k] = int(v.split()[0])
    return out


def thp_sysfs():
    base = Path("/sys/kernel/mm/transparent_hugepage")
    out = {}
    for name in ("enabled", "defrag", "khugepaged/defrag", "hpage_pmd_size"):
        p = base / name
        out[name] = p.read_text().strip() if p.exists() else None
    return out


def schedule(protocol, smoke):
    pc = protocol["pointer_chase"]
    sizes = pc["smoke_sizes_bytes"] if smoke else pc["sizes_bytes"]
    runs = []
    for rnd, modes in enumerate((["4k", "default", "thp"], ["thp", "default", "4k"])):
        for size in sizes:
            for mode in modes:
                runs.append({"phase": "P1", "kind": "pchase", "mode": mode, "size": size, "round": rnd,
                             "accesses": pc["accesses"], "reps": pc["reps"]})
    for size in sizes:
        runs.append({"phase": "P2", "kind": "pchase", "mode": "hugetlb", "size": size, "round": 0,
                     "accesses": pc["accesses"], "reps": pc["reps"]})
    ic = protocol["ic_panel"]
    null_size = pc["smoke_null_size_bytes"] if smoke else pc["null_size_bytes"]
    orders = protocol["block_orders"]
    for k in range(ic["pairs"]):
        for mode in orders[k]:
            runs.append({"phase": "P3", "kind": "ic", "mode": mode, "pair": k})
            if mode != "default":
                runs.append({"phase": "P3", "kind": "pchase", "mode": mode, "size": null_size, "pair": k,
                             "accesses": pc["null_accesses"], "reps": pc["null_reps"]})
    for k in range(protocol["rho_panel"]["pairs"]):
        for mode in orders[k]:
            runs.append({"phase": "P4", "kind": "rho", "mode": mode, "pair": k})
    for i, r in enumerate(runs):
        r["serial"] = i
    return runs


def argv_for(run, protocol, args):
    if run["kind"] == "pchase":
        return [str(args.pchase), str(run["size"]), run["mode"], str(run["accesses"]), str(run["reps"]),
                str(protocol["pointer_chase"]["seed"])]
    q0 = "%s,%s" % tuple(protocol["inputs"]["q0"])
    common = [sys.executable, str(HERE / "thp_arm.py"), "--policy", run["mode"], "--off-cpu", str(args.off_cpu)]
    if run["kind"] == "ic":
        inp = protocol["inputs"]
        return common + ["--arm", "ic_" + run["mode"], "--kind", "ic_online_cached", "--panel", "q0",
                         "--binary", str(args.bin_dir / "ic_online_logcache_r770"), "--point", q0,
                         "--base", str(RECONCILE / inp["base"]), "--base-hash", inp["base_hash"],
                         "--rank-seed", str(inp["rank_seed"]), "--columns", str(inp["orbit_columns"]),
                         "--log-table", str(args.log_table)]
    rp = protocol["rho_panel"]
    return common + ["--arm", "rho_" + run["mode"], "--kind", "rho_tuned", "--panel", "q0",
                     "--binary", str(args.bin_dir / "rho_tuned_r770"), "--point", q0,
                     "--seed", str(rp["seed"]), "--config", str(RECONCILE / rp["config"])]


def parse(run, stdout):
    if run["kind"] == "pchase":
        for line in stdout.splitlines():
            if line.startswith("{"):
                return json.loads(line)
        return {}
    out = {}
    for line in stdout.splitlines():
        if line.startswith("pages_json="):
            out["pages"] = json.loads(line.split("=", 1)[1])
        elif "online_ms=" in line and "verified=" in line:
            out["fields"] = dict(w.split("=", 1) for w in line.split() if "=" in w)
    return out


def one(run, protocol, args, receipt, cgroup):
    argv = argv_for(run, protocol, args)
    binary = argv[0] if run["kind"] == "pchase" else argv[argv.index("--binary") + 1]
    before_sha = sha256(binary)
    cpus = {args.cpu}
    before = ib.counters(cpus, cgroup)
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    mem0 = meminfo()
    t0 = time.monotonic_ns()
    proc = subprocess.Popen(argv, cwd=str(HERE), env=ib.benchmark_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            preexec_fn=lambda: os.sched_setaffinity(0, {args.cpu}))
    timeout = protocol["timeouts_s"][run["kind"]]
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    wall_ms = (time.monotonic_ns() - t0) / 1e6
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    after = ib.counters(cpus, cgroup)
    stem = "%05d" % run["serial"]
    (receipt / "runs" / (stem + ".stdout.txt")).write_text(stdout)
    (receipt / "runs" / (stem + ".stderr.txt")).write_text(stderr)
    noise = ib.noise(before, after, ru0, ru1, "tier1")
    parsed = parse(run, stdout)
    issues = []
    if proc.returncode != 0:
        issues.append("nonzero exit %d" % proc.returncode)
    if timed_out:
        issues.append("timeout")
    if sha256(binary) != before_sha:
        issues.append("binary changed during the run")
    if run["kind"] != "pchase" and parsed.get("fields", {}).get("verified") != "1":
        issues.append("missing verified=1")
    if run["kind"] == "pchase" and parsed.get("status") != "ok":
        issues.append("pchase status %s" % parsed.get("status"))
    row = dict(run, argv=argv, binary_sha256=before_sha, returncode=proc.returncode, timed_out=timed_out,
               process_wall_ms=wall_ms, issues=issues,
               status="valid" if not issues else "invalid",
               noise=noise, meminfo_before=mem0, meminfo_after=meminfo(),
               child_cpu_user_ms=(ru1.ru_utime - ru0.ru_utime) * 1000,
               child_cpu_system_ms=(ru1.ru_stime - ru0.ru_stime) * 1000,
               child_peak_rss_kb_cumulative=ru1.ru_maxrss, parsed=parsed)
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin-dir", type=Path, required=True)
    ap.add_argument("--pchase", type=Path, required=True)
    ap.add_argument("--log-table", type=Path, required=True)
    ap.add_argument("--receipt-dir", type=Path, required=True)
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--off-cpu", type=int, required=True)
    ap.add_argument("--hugetlb-pages", type=int, default=0, help="pages the workflow reserved (0: skip P2)")
    ap.add_argument("--smoke", action="store_true", help="reduced sizes and pairs; not evidence")
    ap.add_argument("--only", choices=("P1", "P2", "P3", "P4"), action="append")
    args = ap.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    if args.smoke:
        protocol["ic_panel"]["pairs"] = protocol["smoke"]["ic_pairs"]
        protocol["rho_panel"]["pairs"] = protocol["smoke"]["rho_pairs"]
    receipt = args.receipt_dir
    (receipt / "runs").mkdir(parents=True, exist_ok=True)
    cgroup = ib.current_cgroup()
    runs = schedule(protocol, args.smoke)
    start = {"protocol_sha256": sha256(HERE / "protocol.json"), "smoke": args.smoke, "cpu": args.cpu,
             "off_cpu": args.off_cpu, "cgroup": str(cgroup), "host": ib.host_probe(), "thp_sysfs": thp_sysfs(),
             "meminfo": meminfo(), "hugetlb_pages_reserved": args.hugetlb_pages,
             "isolated_bench_sha256": sha256(REPO / "scripts/isolated_bench.py"),
             "thp_arm_sha256": sha256(HERE / "thp_arm.py"),
             "reconcile_arm_sha256": sha256(RECONCILE / "arm.py"),
             "pchase_sha256": sha256(args.pchase), "planned_runs": len(runs)}
    tag = "-".join(args.only) if args.only else "all"
    (receipt / ("runner_start_%s.json" % tag)).write_text(json.dumps(start, indent=1, sort_keys=True) + "\n")
    with (receipt / "runs.jsonl").open("a") as out:
        for run in runs:
            if args.only and run["phase"] not in args.only:
                continue
            if run["phase"] == "P2":
                need = run["size"] // (2 << 20)
                if need > args.hugetlb_pages:
                    row = dict(run, status="skipped", issues=["hugetlb pages reserved %d < %d needed"
                                                             % (args.hugetlb_pages, need)])
                    out.write(json.dumps(row, sort_keys=True) + "\n")
                    out.flush()
                    continue
            row = one(run, protocol, args, receipt, cgroup)
            out.write(json.dumps(row, sort_keys=True) + "\n")
            out.flush()
            print(json.dumps({"serial": row["serial"], "phase": row["phase"], "kind": row["kind"],
                              "mode": row["mode"], "status": row["status"], "wall_ms": round(row["process_wall_ms"], 1)}),
                  flush=True)
    (receipt / ("runner_end_%s.json" % tag)).write_text(json.dumps({"meminfo": meminfo(), "thp_sysfs": thp_sysfs()},
                                                        indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
