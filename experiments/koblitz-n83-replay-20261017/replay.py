#!/usr/bin/env python3
"""Replay rank block K1 of koblitz-n83-stacked-20261016 and time one cold K600
base construction, on whatever host the job lands on (PROTOCOL.md).

Every run goes through the stacked experiment's own `run_schedule.one()` and
`arm.py`, unchanged: the same pinned process, clean environment, Tier 1
counters and noise gate, factor-log check against B's archived table and
receipt format. Six runs, in this frozen order, on one pinned CPU:

  R1 kS  K1 point s000, rank seed 101   (archived: run 38862448935 serial 42)
  R2 kP  K1 point s000, rank seed 101   (archived: serial 43)
  R3 kP  same
  R4 kS  same
  R5 cS  Q0, seed 7, retained K600 base (base_n83_K600.jsonl)  -- control
  R6 cS  Q0, seed 7, base argument `construct:83:1:600`         -- construction

R6 differs from R5 only in the producer's first argument: the producer's own
`construct:<n>:<a>:<columns>` path (scan x from 1, rational lifts, cofactor
projection, first 600 distinct signed-Frobenius orbits), the constructor the
n83-compact-orbit-size-sweep-20261012 screen used for this base. Its
`timing_ms.base_load` is the construction time X (plus the same parsing-free
setup start); R5's `base_load` is the retained-file load on the same host.

`analyze` reads the receipts and the archived K1 records and writes
`replay_result.json` and `replay_result.md`. Nothing is re-run.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
STACKED = REPO / "experiments" / "koblitz-n83-stacked-20261016"
ARCHIVE = STACKED / "run_github_38862448935" / "panel"
sys.path.insert(0, str(STACKED))
import run_schedule  # noqa: E402  (the stacked experiment's runner, unchanged)

CONSTRUCT = "construct:83:1:600"
ARCHIVED = {"kS": "00042", "kP": "00043"}
ORDER = [("R1", "kS"), ("R2", "kP"), ("R3", "kP"), ("R4", "kS"), ("R5", "cS"), ("R6", "cS")]
FIRST = 100


def k1_and_q0():
    protocol = json.loads((STACKED / "protocol.json").read_text())
    schedule = json.loads((STACKED / "schedule.json").read_text())
    k1 = {}
    for segment in schedule["segments"]:
        if segment["id"] == "K1":
            for run in segment["runs"]:
                k1[run["arm"]] = run
    assert k1["kS"]["serial"] == 42 and k1["kP"]["serial"] == 43, "K1 is not the archived block"
    assert k1["kS"]["seed"] == k1["kP"]["seed"] == 101
    q0 = None
    for segment in schedule["segments"]:
        for run in segment["runs"]:
            if run["point_id"] == "q0" and run["arm"] == "cS":
                q0 = run
    assert q0 is not None and q0["seed"] == 7
    return protocol, k1, q0


def runs():
    _, k1, q0 = k1_and_q0()
    out = []
    for serial, (label, arm) in enumerate(ORDER, start=1):
        source = q0 if arm == "cS" else k1[arm]
        out.append({"serial": serial, "label": label, "arm": arm, "point_id": source["point_id"],
                    "point": source["point"], "seed": source["seed"], "slice": None,
                    "construct": label == "R6", "archived_serial": source["serial"]})
    return out


def execute(args):
    protocol, _, _ = k1_and_q0()
    if run_schedule.sha256(args.log_table) != protocol["online"]["factor_log_table_sha256"]:
        raise SystemExit("factor-log table differs from the protocol's")
    receipt_dir = args.receipt_dir.resolve()
    (receipt_dir / "runs").mkdir(parents=True, exist_ok=False)
    cgroup = run_schedule.ib.current_cgroup()
    original_command = run_schedule.command

    def command(protocol, run, args, receipt_dir):
        argv = original_command(protocol, run, args, receipt_dir)
        if run.get("construct"):
            argv[argv.index("--base") + 1] = CONSTRUCT
        return argv

    run_schedule.command = command
    start = {"cpu": args.cpu, "host": run_schedule.ib.host_probe(), "cgroup": str(cgroup),
             "replay_sha256": run_schedule.sha256(Path(__file__)),
             "stacked_protocol_sha256": run_schedule.sha256(STACKED / "protocol.json"),
             "stacked_schedule_sha256": run_schedule.sha256(STACKED / "schedule.json"),
             "arm_wrapper_sha256": run_schedule.sha256(STACKED / "arm.py"),
             "runner_sha256": run_schedule.sha256(STACKED / "run_schedule.py"),
             "binaries_sha256": {name: run_schedule.sha256(args.bin_dir / name)
                                 for name in ("ic_online_stacked_r770",)},
             "order": [[run["label"], run["arm"], run["point_id"], run["seed"], run["construct"]]
                       for run in runs()]}
    (receipt_dir / "runner_start.json").write_text(json.dumps(start, indent=2, sort_keys=True) + "\n")
    with (receipt_dir / "runs.jsonl").open("w") as ledger:
        for run in runs():
            row = run_schedule.one(protocol, run, args, receipt_dir, cgroup)
            row.update(label=run["label"], construct=run["construct"],
                       archived_serial=run["archived_serial"])
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            print(json.dumps({"label": run["label"], "arm": run["arm"], "status": row["status"],
                              "issues": row["issues"], "wall_ms": row["process_wall_ms"]}), flush=True)


def decode(stdout_path):
    text = Path(stdout_path).read_text()
    lines = [line for line in text.splitlines() if line.startswith("raw_b64=")]
    if len(lines) != 1:
        return None, None
    raw = base64.b64decode(lines[0][len("raw_b64="):])
    record = json.loads(raw)
    summary = [r for r in record["records"] if r.get("kind") == "compact_orbit_dlp_summary"]
    fields = dict(word.split("=", 1) for word in text.splitlines()[-1].split() if "=" in word)
    if fields.get("raw_result_sha256") != hashlib.sha256(raw).hexdigest():
        return record, None
    return record, (summary[0] if summary else None)


def digest(values):
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def per_probe(summary, first=None):
    ns, probes = summary["rank_attempt_ns"], summary["rank_attempt_probes"]
    if first is not None:
        ns, probes = ns[:first], probes[:first]
    return sum(ns) / sum(probes)


def analyze(args):
    receipt_dir = args.receipt_dir.resolve()
    rows = [json.loads(line) for line in (receipt_dir / "runs.jsonl").read_text().splitlines() if line]
    archived = {}
    for arm, serial in ARCHIVED.items():
        _, summary = decode(ARCHIVE / "runs" / (serial + ".stdout.txt"))
        archived[arm] = summary
    result = {"runs": [], "checks": {}, "host": {}}
    host_file = receipt_dir.parent / "host-class.json"
    if host_file.exists():
        result["host"] = json.loads(host_file.read_text())
    rank = {"kS": [], "kP": []}
    cold = {}
    for row in rows:
        record, summary = decode(receipt_dir / row["stdout_file"])
        entry = {"label": row["label"], "arm": row["arm"], "status": row["status"],
                 "issues": row["issues"], "contention_flags": row["contention_flags"],
                 "process_wall_ms": row["process_wall_ms"], "raw_ok": summary is not None}
        if summary is not None and row["arm"] in rank:
            want = archived[row["arm"]]
            probes = summary.get("rank_attempt_probes") or []
            entry.update({
                "rank_attempts": summary.get("rank_attempts"),
                "rank_probes_total": summary.get("rank_probes_total"),
                "rank_root_calls_total": summary.get("rank_root_calls_total"),
                "rank_stage_ms": summary["timing_ms"]["rank_stage"],
                "probes_first100_equal_archived": probes[:FIRST] == want["rank_attempt_probes"][:FIRST],
                "probes_all_equal_archived": probes == want["rank_attempt_probes"],
                "probes_digest": digest(probes),
                "relations_blake3_equal_archived":
                    summary.get("rank_relations_blake3") == want["rank_relations_blake3"],
                "ns_per_probe_first100": per_probe(summary, FIRST),
                "ns_per_probe_all_attempts": per_probe(summary),
                "ns_per_probe_rank_stage": summary["timing_ms"]["rank_stage"] * 1e6 / summary["rank_probes_total"],
            })
            rank[row["arm"]].append(entry)
        if summary is not None and row["arm"] == "cS":
            entry.update({"base_source": summary.get("base_source"),
                          "base_scanned_x": summary.get("base_scanned_x"),
                          "base_hash": summary.get("base_hash"),
                          "base_load_ms": summary["timing_ms"]["base_load"],
                          "setup_total_ms": summary["timing_ms"]["setup_total"],
                          "cold_in_process_ms": summary.get("cold_in_process_ms")})
            cold[row["label"]] = entry
        result["runs"].append(entry)

    def ratio(key):
        p = [e[key] for e in rank["kP"]]
        s = [e[key] for e in rank["kS"]]
        if not p or not s:
            return None
        return (sum(p) / len(p)) / (sum(s) / len(s))

    def pooled_rank_stage():
        if not rank["kP"] or not rank["kS"]:
            return None
        p = sum(e["rank_stage_ms"] for e in rank["kP"]) / sum(e["rank_probes_total"] for e in rank["kP"])
        s = sum(e["rank_stage_ms"] for e in rank["kS"]) / sum(e["rank_probes_total"] for e in rank["kS"])
        return p / s

    arch_first = per_probe(archived["kP"], FIRST) / per_probe(archived["kS"], FIRST)
    arch_stage = ((archived["kP"]["timing_ms"]["rank_stage"] / archived["kP"]["rank_probes_total"]) /
                  (archived["kS"]["timing_ms"]["rank_stage"] / archived["kS"]["rank_probes_total"]))
    every_rank = rank["kS"] + rank["kP"]
    result["checks"] = {
        "all_runs_valid": all(row["status"] == "valid" for row in rows) and len(rows) == len(ORDER),
        "probes_first100_equal_archived": bool(every_rank) and len(every_rank) == 4 and
            all(e["probes_first100_equal_archived"] for e in every_rank),
        "probes_all_equal_archived": bool(every_rank) and len(every_rank) == 4 and
            all(e["probes_all_equal_archived"] for e in every_rank),
        "relations_equal_archived": bool(every_rank) and len(every_rank) == 4 and
            all(e["relations_blake3_equal_archived"] for e in every_rank),
        "constructed_base_hash_equals_retained":
            cold.get("R5", {}).get("base_hash") is not None and
            cold.get("R6", {}).get("base_hash") == cold["R5"]["base_hash"],
        "R6_constructed": cold.get("R6", {}).get("base_source") == "constructed_in_process_x_scan",
        "R5_retained": cold.get("R5", {}).get("base_source") == "retained_header",
    }
    result["per_probe_wall_ratio_kP_over_kS"] = {
        "primary_rank_stage_pooled": pooled_rank_stage(),
        "first100_attempts_mean": ratio("ns_per_probe_first100"),
        "all_attempts_mean": ratio("ns_per_probe_all_attempts"),
        "archived_K1_rank_stage": arch_stage,
        "archived_K1_first100": arch_first,
        "archived_both_blocks_rank_stage": 2.2837135233640566,
        "meaning": "wall time per probe, kP over kS; a kP probe (full canonicalization) and a kS probe (lift_scan) are not the same work, so this mixes per-probe work with host and memory-system effects; it is not a host-speed factor",
    }
    if "R5" in cold and "R6" in cold:
        result["construction"] = {
            "X_ms_constructed_base_load": cold["R6"]["base_load_ms"],
            "retained_base_load_ms_same_host": cold["R5"]["base_load_ms"],
            "X_minus_retained_ms": cold["R6"]["base_load_ms"] - cold["R5"]["base_load_ms"],
            "base_scanned_x": cold["R6"]["base_scanned_x"],
        }
    passed = result["checks"]["all_runs_valid"] and result["checks"]["probes_all_equal_archived"] and \
        result["checks"]["relations_equal_archived"] and result["checks"]["constructed_base_hash_equals_retained"] and \
        result["checks"]["R6_constructed"] and result["checks"]["R5_retained"]
    result["verdict"] = "replay_pass" if passed else "replay_fail"
    (receipt_dir / "replay_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    ratio_block = result["per_probe_wall_ratio_kP_over_kS"]
    lines = ["# n=83 K1 replay", "", "verdict: **%s**" % result["verdict"], "",
             "host: %s" % result["host"].get("cpu_model"), "",
             "| check | value |", "| --- | --- |"]
    lines += ["| %s | %s |" % item for item in sorted(result["checks"].items())]
    lines += ["", "| per-probe wall ratio kP / kS | value |", "| --- | --- |"]
    lines += ["| %s | %s |" % (key, value) for key, value in sorted(ratio_block.items()) if key != "meaning"]
    if "construction" in result:
        lines += ["", "| construction | value |", "| --- | --- |"]
        lines += ["| %s | %s |" % item for item in sorted(result["construction"].items())]
    (receipt_dir / "replay_result.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    run = sub.add_parser("run")
    run.add_argument("--bin-dir", required=True, type=Path)
    run.add_argument("--log-table", required=True, type=Path)
    run.add_argument("--receipt-dir", required=True, type=Path)
    run.add_argument("--cpu", required=True, type=int)
    run.add_argument("--python", type=Path, default=Path(sys.executable))
    check = sub.add_parser("analyze")
    check.add_argument("--receipt-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "run":
        args.bin_dir = args.bin_dir.resolve(strict=True)
        args.log_table = args.log_table.resolve(strict=True)
        execute(args)
        return 0
    return analyze(args)


if __name__ == "__main__":
    sys.exit(main())
