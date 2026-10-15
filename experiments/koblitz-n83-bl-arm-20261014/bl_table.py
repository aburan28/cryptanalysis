#!/usr/bin/env python3
"""Build the n=83 BL table at the IC's setup budget, then check it three ways.

`precompute`: one process on the execution CPU runs the chosen implementation's
BL precomputation (`rho_reference.value` in protocol.json) with the frozen
dp_bits and seeds, stopping at the first 256-round boundary after its walk has
run for P_IC milliseconds, where P_IC = rank stage + setup_total of the in-job
IC precompute receipt (`ic_precompute.py`). It writes `table.bin` and
`precompute_receipt.json` (the producer's counts, the table's SHA-256 and
BLAKE3, wall time, the budget match).

`check`: three independent checks of the stored table, run together after the
precomputation and before any online arm (none of them is timed):
* regeneration: the same precomputation stopped at the recorded round count, on
  another CPU, must write a byte-identical file (SHA-256 and BLAKE3);
* every record, in the producer's arithmetic (`verify-table`, the verify CPUs,
  after the regeneration has finished):
  log in [1, r), distinguished, canonical, [a]G = (x, y);
* a seeded sample of records in the pinned pure-Python oracle (`oracle.py`, not
  the producer's code): [a]G = (x, y).

`--impl` overrides `rho_reference.value` for the local smoke only and is
recorded in every receipt.
"""

import argparse
import concurrent.futures
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bl_tools as bt  # noqa: E402

SNAPSHOT = HERE / "snapshot"
CURVE = (83, 1)


def chosen(protocol, override):
    value = protocol["rho_reference"]["value"]
    if override:
        if override not in protocol["rho_step_implementations"]:
            raise SystemExit("unknown implementation " + override)
        return override, True
    if value is None:
        raise SystemExit("rho_reference.value is not set in protocol.json: the rho step implementation "
                         "is still open (item 2); nothing at n=83 runs until it is set")
    if value not in protocol["rho_step_implementations"]:
        raise SystemExit("rho_reference.value names no declared implementation")
    return value, False


def precompute(args, protocol):
    impl, overridden = chosen(protocol, args.impl)
    spec = protocol["rho_step_implementations"][impl]["bl"]
    bl = protocol["bl"]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.budget_ms is not None:
        budget_ms, budget_source = args.budget_ms, "explicit --budget-ms (smoke only)"
        if not args.smoke:
            raise SystemExit("--budget-ms is for the local smoke only")
    else:
        ic = json.loads(args.ic_receipt.read_text())
        if ic.get("status") != "PASS":
            raise SystemExit("the IC precompute did not pass; no budget")
        budget_ms, budget_source = float(ic["P_IC_ms"]), str(args.ic_receipt)
    table = out / "table.bin"
    argv, env = bt.precompute_command(spec, args.bin_dir, CURVE, bl["dp_bits"], bl["bl_jump_seed"],
                                      bl["precompute_seed"], table, {"budget_ms": budget_ms})
    code, stdout, stderr, wall_s, usage = bt.run_pinned(argv, env, args.cpu, out / "stdout.txt",
                                                        timeout=bl["precompute_timeout_s"])
    (out / "stderr.txt").write_text(stderr)
    summary = ([r for r in bt.json_lines(stdout) if r.get("kind") == "bl_precompute"] or [{}])[-1]
    receipt = {"implementation": impl, "implementation_overridden_for_smoke": overridden,
               "spec": spec, "dp_bits": bl["dp_bits"], "command": argv,
               "env": {k: v for k, v in env.items() if k.startswith("KIC_") or k in ("RAYON_NUM_THREADS",)},
               "cpu": args.cpu, "exit_code": code, "process_wall_s": wall_s, "usage": usage,
               "budget_ms": budget_ms, "budget_source": budget_source, "producer": summary,
               "binary_sha256": bt.sha256(argv[0])}
    checks = {"exit_zero": code == 0, "summary_present": bool(summary),
              "table_written": table.exists()}
    if summary:
        precompute_ms = summary["precompute_ms"]
        checks["budget_reached"] = precompute_ms >= budget_ms
        checks["budget_not_overrun_by_more_than_1pct"] = precompute_ms <= budget_ms * 1.01 + 50
        checks["entries_equal_new_points"] = summary["table_entries"] == summary["new_points"]
        receipt["precompute_over_budget"] = precompute_ms / budget_ms
    if table.exists():
        receipt["table_sha256"] = bt.sha256(table)
        receipt["table_bytes"] = table.stat().st_size
        checks["blake3_recorded"] = bool(summary.get("table_blake3"))
        checks["size_matches_entries"] = receipt["table_bytes"] == summary.get("table_entries", -1) * 40
    receipt["checks"] = checks
    receipt["status"] = "PASS" if all(checks.values()) else "FAIL"
    (out / "precompute_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "checks": checks,
                      "entries": summary.get("table_entries"), "precompute_ms": summary.get("precompute_ms")},
                     sort_keys=True))
    if receipt["status"] != "PASS":
        raise SystemExit(3)


def oracle_sample(table, count, seed):
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)
    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json").read_text())
    curve = panel.cached_curve(dict(beats["beats"]["koblitz.compact_orbit.n83_single_target"]["curve_fixture"]))
    entries = table.stat().st_size // 40
    rng = random.Random(seed)
    picks = sorted(rng.sample(range(entries), min(count, entries)))
    bad = []
    with table.open("rb") as stream:
        for index in picks:
            stream.seek(index * 40)
            record = stream.read(40)
            x = int.from_bytes(record[:16], "little")
            y = int.from_bytes(record[16:32], "little")
            log = int.from_bytes(record[32:], "little")
            if not (0 < log < curve.r) or curve.mul(curve.g, log) != (x, y):
                bad.append(index)
    return {"checker": "oracle.py pure-Python GF(2^83) arithmetic of the pinned harness, not the producer",
            "sample": len(picks), "sample_seed": seed, "entries": entries, "bad": bad[:20],
            "status": "PASS" if not bad else "FAIL"}


def check(args, protocol):
    receipt = json.loads((args.receipt_dir / "precompute_receipt.json").read_text())
    if receipt["status"] != "PASS":
        raise SystemExit("precompute receipt did not pass")
    impl = receipt["implementation"]
    spec = protocol["rho_step_implementations"][impl]["bl"]
    bl = protocol["bl"]
    summary = receipt["producer"]
    table = args.receipt_dir / "table.bin"
    regen_dir = args.receipt_dir / "regeneration"
    regen_dir.mkdir()
    regen_table = regen_dir / "table.bin"
    regen_argv, regen_env = bt.precompute_command(spec, args.bin_dir, CURVE, bl["dp_bits"], bl["bl_jump_seed"],
                                                  bl["precompute_seed"], regen_table,
                                                  {"stop_rounds": summary["rounds"]})
    verify_argv, verify_env = bt.verify_command(spec, args.bin_dir, CURVE, bl["dp_bits"], table,
                                                summary["table_blake3"], len(args.verify_cpus))
    started = time.time()

    def verify_job():
        # The verifier's threads inherit an affinity mask of the verify CPUs.
        import subprocess
        proc = subprocess.run(verify_argv, env=verify_env, capture_output=True, text=True,
                              preexec_fn=lambda: os.sched_setaffinity(0, set(args.verify_cpus)))
        return proc.returncode, proc.stdout, proc.stderr

    # Regeneration and the oracle sample run together; the record-by-record
    # check runs after them on all verify CPUs (two full tables in memory at
    # once would not fit 16 GB at the largest declared T).
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        regen_future = pool.submit(bt.run_pinned, regen_argv, regen_env, args.regen_cpu, regen_dir / "stdout.txt",
                                   bl["precompute_timeout_s"] * 2)
        oracle_future = pool.submit(oracle_sample, table, bl["oracle_sample"], bl["oracle_sample_seed"])
        regen_code, regen_out, regen_err, regen_wall, _ = regen_future.result()
        oracle = oracle_future.result()
    if regen_table.exists() and bt.sha256(regen_table) == receipt["table_sha256"]:
        regen_sha = receipt["table_sha256"]
        regen_table.unlink()  # identical bytes; keep one copy
    else:
        regen_sha = bt.sha256(regen_table) if regen_table.exists() else None
    verify_code, verify_out, verify_err = verify_job()
    regen_summary = ([r for r in bt.json_lines(regen_out) if r.get("kind") == "bl_precompute"] or [{}])[-1]
    verification = ([r for r in bt.json_lines(verify_out) if r.get("kind") == "bl_table_verification"] or [{}])[-1]
    result = {
        "implementation": impl, "table_sha256": receipt["table_sha256"], "table_blake3": summary["table_blake3"],
        "regeneration": {"command": regen_argv, "cpu": args.regen_cpu, "exit_code": regen_code,
                         "wall_s": regen_wall, "sha256": regen_sha, "blake3": regen_summary.get("table_blake3"),
                         "rounds": regen_summary.get("rounds"), "steps": regen_summary.get("steps"),
                         "stderr_tail": regen_err[-2000:]},
        "producer_verification": dict(verification, exit_code=verify_code, cpus=args.verify_cpus,
                                      stderr_tail=verify_err[-2000:]),
        "oracle_sample": oracle, "wall_s": time.time() - started,
    }
    checks = {
        "regeneration_byte_identical": regen_code == 0 and regen_sha == receipt["table_sha256"] and
        regen_summary.get("table_blake3") == summary["table_blake3"],
        "regeneration_same_counts": (regen_summary.get("rounds"), regen_summary.get("steps"),
                                     regen_summary.get("table_entries")) ==
        (summary["rounds"], summary["steps"], summary["table_entries"]),
        "every_record_verified_by_producer": verify_code == 0 and verification.get("status") == "PASS" and
        verification.get("entries") == summary["table_entries"],
        "oracle_sample_verified": oracle["status"] == "PASS",
    }
    result["checks"] = checks
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    (args.receipt_dir / "table_checks.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "checks": checks}, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    go = sub.add_parser("precompute")
    go.add_argument("--bin-dir", required=True, type=Path)
    go.add_argument("--cpu", required=True, type=int)
    go.add_argument("--out", required=True, type=Path)
    go.add_argument("--ic-receipt", type=Path)
    go.add_argument("--budget-ms", type=float)
    go.add_argument("--impl")
    go.add_argument("--smoke", action="store_true")
    ck = sub.add_parser("check")
    ck.add_argument("--bin-dir", required=True, type=Path)
    ck.add_argument("--receipt-dir", required=True, type=Path)
    ck.add_argument("--regen-cpu", required=True, type=int)
    ck.add_argument("--verify-cpus", required=True, type=lambda v: [int(c) for c in v.split(",")])
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    if args.action == "precompute":
        if args.impl and not args.smoke:
            raise SystemExit("--impl is for the local smoke only")
        if args.budget_ms is None and args.ic_receipt is None:
            raise SystemExit("give --ic-receipt")
        precompute(args, protocol)
    else:
        check(args, protocol)


if __name__ == "__main__":
    main()
