#!/usr/bin/env python3
"""Run the IC rank stage once, write the factor-log table, and verify it independently.

Adapted from B's `precompute.py` (experiments/koblitz-single-target-n83-tier1-20261014/),
with this experiment's snapshot, binary name and protocol. The produced table must
equal B's archived table (run 38523707244) in every field except its own
recorded rank-stage time; the IC arms then load B's archived file, whose
SHA-256 the protocol binds.

`run`: one in-process IC run on the frozen point Q0 with KIC_LOG_TABLE_OUT
set, pinned to one CPU with one thread. It is a complete cold IC solve
(base, index, sequential rank, linear algebra, Q0 online) and its timers give
the reusable setup: P_IC = rank stage + setup_total (base load, normal basis
and self-test, root index, linear algebra), the BL budget and the IC part of
the cold costs.
`verify`: re-checks every [L_j]G = R_j of a table in the pinned harness's
pure-Python oracle, independently of the producer, and checks the table's
identity fields against the base header.
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
SNAPSHOT = HERE / "snapshot"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_oracle_curve(protocol):
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402
    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json").read_text())
    return panel.cached_curve(dict(beats["beats"][protocol["harness"]["beat_id"]]["curve_fixture"]))


def verify_table(table_path, base_path, protocol, curve=None):
    table = json.loads(Path(table_path).read_text())
    header = json.loads(Path(base_path).read_text().splitlines()[0])
    curve = curve or load_oracle_curve(protocol)
    reps = header["factor_base_representatives"]
    logs = [int(v) for v in table["logs"]]
    checks = {
        "kind": table.get("kind") == "compact_orbit_factor_log_table",
        "n_a_r": (table.get("n"), table.get("a"), table.get("subgroup_order")) ==
                 (header["n"], header["a"], str(header["subgroup_order"])),
        "base_hash": table.get("base_hash") == header["base_hash"],
        "width": table.get("orbit_columns") == len(reps) == len(logs),
        "range": all(0 < log < curve.r for log in logs),
    }
    bad = [j for j, (log, rep) in enumerate(zip(logs, reps))
           if curve.mul(curve.g, log) != curve.decode([int(rep[0]), int(rep[1])])]
    checks["every_log_maps_G_to_its_representative"] = not bad
    return {"table": str(table_path), "table_sha256": sha256(table_path), "columns": len(logs),
            "checks": checks, "bad_columns": bad[:20], "status": "PASS" if all(checks.values()) else "FAIL",
            "checker": "oracle.py pure-Python field arithmetic (pinned harness), not the producer"}


def run(args, protocol):
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    table = out_dir / "factor_logs_n83_K600.json"
    target = out_dir / "q0.jsonl"
    q0 = json.loads((HERE / protocol["inputs"]["targets_file"]).read_text())["q0"]["point"]
    if sha256(HERE / protocol["inputs"]["targets_file"]) != protocol["inputs"]["targets_sha256"]:
        raise SystemExit("targets file differs from the protocol")
    target.write_text(json.dumps(q0, separators=(",", ":")) + "\n")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
           "KIC_LOG_TABLE_OUT": str(table)}
    base = SNAPSHOT / protocol["inputs"]["base"]
    command = [str(args.binary), str(base), str(target), str(protocol["precompute"]["rank_seed"]),
               str(out_dir / "ic_q0.jsonl")]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic_ns()
    with (out_dir / "summary.jsonl").open("w") as stdout, (out_dir / "stderr.txt").open("w") as stderr:
        proc = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr,
                                preexec_fn=lambda: os.sched_setaffinity(0, {args.cpu}))
        try:
            code = proc.wait(timeout=protocol["precompute"]["timeout_s"])
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()
    wall_s = (time.monotonic_ns() - started) / 1e9
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    summary = [json.loads(line) for line in (out_dir / "summary.jsonl").read_text().splitlines()
               if line.startswith("{")]
    summary = summary[-1] if summary else {}
    records = [json.loads(line) for line in (out_dir / "ic_q0.jsonl").read_text().splitlines()
               if line.strip()] if (out_dir / "ic_q0.jsonl").exists() else []
    receipt = {
        "command": command, "env": env, "cpu": args.cpu, "exit_code": code, "process_wall_s": wall_s,
        "user_s": after.ru_utime - before.ru_utime, "system_s": after.ru_stime - before.ru_stime,
        "max_rss_bytes": after.ru_maxrss * 1024, "binary_sha256": sha256(args.binary),
        "timing_ms": summary.get("timing_ms"), "setup_complete_ns": summary.get("setup_complete_ns"),
        "rank": summary.get("rank"), "rank_relations": summary.get("rank_relations"),
        "rank_probes_total": summary.get("rank_probes_total"),
        "rank_probes_mean": summary.get("rank_probes_mean"), "base_hash": summary.get("base_hash"),
        "factor_log_table": summary.get("factor_log_table"), "peak_rss_bytes": summary.get("peak_rss_bytes"),
        "q0_record": records[0] if len(records) == 1 else None,
        "noise_gated": False,
        "note": "one process on one pinned CPU outside isolated_bench; instance-observed, not noise gated",
    }
    checks = {
        "exit_zero": code == 0,
        "rank_full": summary.get("rank") == 600 and summary.get("rank_relations", 0) >= 600,
        "base_hash": summary.get("base_hash") == protocol["inputs"]["base_hash"],
        "q0_verified": bool(records) and records[0].get("group_verified") is True,
        "table_written": table.exists(),
    }
    if table.exists():
        receipt["table_sha256"] = sha256(table)
        receipt["independent_table_check"] = verify_table(table, base, protocol)
        checks["table_verified_independently"] = receipt["independent_table_check"]["status"] == "PASS"
        # The table file records its own rank-stage wall time under
        # provenance.rank_stage_ms, so bytes cannot repeat across runs; every
        # other field (the 600 logs, n, a, r, base hash, width, the rest of the
        # provenance) must equal B's archived table, whose bytes the IC arms load.
        archived_path = HERE / protocol["inputs"]["factor_log_table_archived"]
        archived = json.loads(archived_path.read_text())
        produced = json.loads(table.read_text())
        for value in (archived, produced):
            value.get("provenance", {}).pop("rank_stage_ms", None)
        checks["archived_table_digest_as_bound"] = (
            sha256(archived_path) == protocol["inputs"]["factor_log_table_archived_sha256"])
        checks["matches_B_archived_table_except_timing"] = produced == archived
    timing = summary.get("timing_ms") or {}
    if "rank_stage" in timing and "setup_total" in timing:
        receipt["P_IC_ms"] = timing["rank_stage"] + timing["setup_total"]
        receipt["P_IC_definition"] = protocol["budget"]["definition"]
    checks["P_IC_recorded"] = "P_IC_ms" in receipt
    receipt["checks"] = checks
    receipt["status"] = "PASS" if all(checks.values()) else "FAIL"
    (out_dir / "precompute_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "checks": checks, "wall_s": wall_s}, sort_keys=True))
    if receipt["status"] != "PASS":
        raise SystemExit(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    go = sub.add_parser("run")
    go.add_argument("--binary", required=True, type=Path)
    go.add_argument("--cpu", required=True, type=int)
    go.add_argument("--out", required=True, type=Path)
    check = sub.add_parser("verify")
    check.add_argument("--table", required=True, type=Path)
    check.add_argument("--base", type=Path)
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    if args.action == "run":
        run(args, protocol)
    else:
        result = verify_table(args.table, args.base or SNAPSHOT / protocol["inputs"]["base"], protocol)
        print(json.dumps(result, indent=2, sort_keys=True))
        if result["status"] != "PASS":
            raise SystemExit(3)


if __name__ == "__main__":
    main()
